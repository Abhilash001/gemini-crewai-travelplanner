import asyncio
import os
import re
from fastapi import FastAPI, HTTPException, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import pdfkit
import markdown as md

from common import (
    AIResponse, 
    FlightRequest, 
    HotelRequest,
    HotelsGrouped, 
    ItineraryRequest, 
    logger, 
    extract_recommended_flight_indices,
    extract_recommended_hotel_index,
    format_selected_travel_data, 
    format_travel_data, 
    generate_itinerary, 
    get_ai_recommendation, 
    search_flights, 
    search_google_hotels, 
    search_booking_hotels, 
    strip_code_fence
)

# ==============================================
# 🚀 Initialize FastAPI
# ==============================================
app = FastAPI(title="Travel Planning API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify your frontend URL, e.g. ["http://localhost:4200"]
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods, including OPTIONS
    allow_headers=["*"],
)

# ==============================================
# 🚀 API Endpoints
# ==============================================
@app.post("/search_flights/", response_model=AIResponse)
async def get_flight_recommendations(flight_request: FlightRequest):
    """Search flights and get AI recommendation."""
    try:
        # Search for flights
        flights = await search_flights(flight_request)

        # Handle errors
        if isinstance(flights, dict) and "error" in flights:
            raise HTTPException(status_code=400, detail=flights["error"])

        if not flights:
            raise HTTPException(status_code=404, detail="No flights found")

        # Format flight data for AI
        flights_text = format_travel_data("flights", flights)

        # Get AI recommendation
        ai_recommendation = await get_ai_recommendation("flights", flights_text)

        # Return response
        return AIResponse(
            flights=flights,
            ai_flight_recommendation=ai_recommendation
        )
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status codes
        raise
    except Exception as e:
        logger.exception(f"Flight search endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Flight search error: {str(e)}")


@app.post("/search_hotels/", response_model=AIResponse)
async def get_hotel_recommendations(hotel_request: Optional[List[HotelRequest]] = Body(default=None)):
    """Search hotels and get AI recommendation."""
    try:
        if not hotel_request or len(hotel_request) == 0:
            raise HTTPException(status_code=400, detail="No hotel requests provided")
        # Run hotel searches for each location
        hotel_provider = os.getenv("HOTEL_PROVIDER", "booking").lower()
        semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent searches

        async def search_one(req):
            async with semaphore:
                if hotel_provider == "google":
                    return await search_google_hotels(req)
                else:
                    return await search_booking_hotels(req)

        # Launch all searches, but only 2 run at a time
        hotels_results = await asyncio.gather(*(search_one(req) for req in hotel_request))

        if not hotels_results:
            raise HTTPException(status_code=404, detail="No hotels found")
        
        # Format hotel data for AI and get recommendations for each location
        ai_hotel_recommendations = []
        all_hotels = []
        hotels_grouped = []
        for idx, hotels in enumerate(hotels_results):
            # Handle errors
            if isinstance(hotels, dict) and "error" in hotels:
                raise HTTPException(status_code=400, detail=hotels["error"])
            if not hotels:
                raise HTTPException(status_code=404, detail="No hotels found")
            hotels_grouped.append(HotelsGrouped(
                location=hotel_request[idx].location,
                check_in_date=hotel_request[idx].check_in_date,
                check_out_date=hotel_request[idx].check_out_date,
                hotels=hotels
            ))
            all_hotels.extend(hotels)
            hotels_text = format_travel_data("hotels", hotels)
            ai_hotel_recommendations.append(await get_ai_recommendation("hotels", hotels_text))

        # Return response
        return AIResponse(
            hotels=all_hotels,
            hotels_grouped=hotels_grouped,
            ai_hotel_recommendations=ai_hotel_recommendations
        )
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status codes
        raise
    except Exception as e:
        logger.exception(f"Hotel search endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Hotel search error: {str(e)}")


@app.post("/complete_search/", response_model=AIResponse)
async def complete_travel_search(
    flight_request: FlightRequest,
    hotel_request: Optional[List[HotelRequest]] = Body(default=None),
    special_instructions: Optional[str] = Body(default=None)
):
    """
    Search for flights and multiple hotels concurrently and get AI recommendations for both.
    hotel_request: List of HotelRequest objects (one per location)
    """
    try:
        # If hotel request is not provided, create one from flight request
        if not hotel_request:
            hotel_request = [HotelRequest(
                location=flight_request.destination,
                check_in_date=flight_request.outbound_date,
                check_out_date=flight_request.return_date
            )]

        # Run flight and hotel searches concurrently
        flight_task = asyncio.create_task(get_flight_recommendations(flight_request))
        hotel_task = asyncio.create_task(get_hotel_recommendations(hotel_request))

        # Wait for both tasks to complete
        flight_results, hotel_results = await asyncio.gather(flight_task, hotel_task, return_exceptions=True)

        # Check for exceptions
        if isinstance(flight_results, Exception):
            logger.error(f"Flight search failed: {str(flight_results)}")
            flight_results = AIResponse(flights=[], ai_flight_recommendation="Could not retrieve flights.")

        if isinstance(hotel_results, Exception):
            logger.error(f"Hotel search failed: {str(hotel_results)}")
            hotel_results = AIResponse(hotels=[], ai_hotel_recommendation="Could not retrieve hotels.")

        # --- NEW: Use only recommended flight/hotel for itinerary ---
        dep_idx, ret_idx = extract_recommended_flight_indices(flight_results.ai_flight_recommendation)

        # Select the recommended departure and return flight
        selected_flight = None
        selected_return_flight = None
        if flight_results.flights and 0 <= dep_idx < len(flight_results.flights):
            selected_flight = flight_results.flights[dep_idx]
            if selected_flight.return_flights and 0 <= ret_idx < len(selected_flight.return_flights):
                selected_return_flight = selected_flight.return_flights[ret_idx]
        if selected_flight:
            flight_info = [selected_flight]
            if selected_return_flight:
                # Replace return_flights with only the selected one for formatting
                flight_info[0] = flight_info[0].model_copy(update={"return_flights": [selected_return_flight]})
            selected_flights_text = format_selected_travel_data("flights", flight_info)
        else:
            selected_flights_text = format_travel_data("flights", flight_results.flights[:1])

        # --- NEW: Collect all recommended hotels from each group ---
        # Instead of just a flat list, build a list of (hotel, check_in, check_out)
        recommended_hotels = []
        for idx, hotels_group in enumerate(hotel_results.hotels_grouped or []):
            ai_reco = hotel_results.ai_hotel_recommendations[idx] if hotel_results.ai_hotel_recommendations and idx < len(hotel_results.ai_hotel_recommendations) else ""
            hotel_idx = extract_recommended_hotel_index(ai_reco)
            if hotels_group.hotels and 0 <= hotel_idx < len(hotels_group.hotels):
                recommended_hotels.append({
                    "hotel": hotels_group.hotels[hotel_idx],
                    "check_in": hotels_group.check_in_date,
                    "check_out": hotels_group.check_out_date,
                    "location": hotels_group.location
                })
            elif hotels_group.hotels:
                recommended_hotels.append({
                    "hotel": hotels_group.hotels[0],
                    "check_in": hotels_group.check_in_date,
                    "check_out": hotels_group.check_out_date,
                    "location": hotels_group.location
                })

        selected_hotels_text = format_selected_travel_data("hotels", recommended_hotels)

        # Generate itinerary using only the recommended options
        itinerary = ""
        if selected_flight and recommended_hotels:
            itinerary = await generate_itinerary(
                destination=flight_request.destination,
                flights_text=selected_flights_text,
                hotels_text=selected_hotels_text,
                check_in_date=flight_request.outbound_date,
                check_out_date=flight_request.return_date,
                special_instructions=special_instructions
            )

        # Combine results
        return AIResponse(
            flights=flight_results.flights,
            hotels=hotel_results.hotels,
            hotels_grouped=hotel_results.hotels_grouped,
            ai_flight_recommendation=flight_results.ai_flight_recommendation,
            ai_hotel_recommendations=hotel_results.ai_hotel_recommendations,
            itinerary=itinerary
        )
    except Exception as e:
        logger.exception(f"Complete travel search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Travel search error: {str(e)}")


@app.post("/generate_itinerary/", response_model=AIResponse)
async def get_itinerary(itinerary_request: ItineraryRequest):
    """Generate an itinerary based on provided flight and hotel information."""
    try:
        itinerary = await generate_itinerary(
            destination=itinerary_request.destination,
            flights_text=itinerary_request.flights,
            hotels_text=itinerary_request.hotels,
            check_in_date=itinerary_request.check_in_date,
            check_out_date=itinerary_request.check_out_date
        )

        itinerary = strip_code_fence(itinerary)

        return AIResponse(itinerary=itinerary)
    except ValueError as e:
        logger.exception(f"Itinerary generation error: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Itinerary generation error: {str(e)}")
    except Exception as e:
        logger.exception(f"Itinerary generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Itinerary generation error: {str(e)}")


class MarkdownToPdfRequest(BaseModel):
    markdown: str
    title: str = "Travel Itinerary"

@app.post("/generate_pdf/")
def generate_pdf(req: MarkdownToPdfRequest):
    html_content = md.markdown(req.markdown, extensions=["extra", "smarty"])
    html_content = re.sub(
        r'([\U0001F300-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF\U0001F1E6-\U0001F1FF])',
        r'<span class="emoji">\1</span>',
        html_content
    )
    html_full = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <title>{req.title}</title>
      <link href="https://fonts.googleapis.com/css2?family=Noto+Emoji:wght@400" rel="stylesheet">
      <style>
        body {{ background: #fff; color: #222; font-family: Arial, sans-serif; margin: 2em; }}
        /* Only apply Noto Emoji to emoji characters */
        .emoji {{ font-family: 'Noto Emoji', Arial, sans-serif !important; }}
      </style>
    </head>
    <body>{html_content}</body>
    </html>
    """
    wkhtmltopdf_path = os.path.join(os.path.dirname(__file__), 'wkhtmltox', 'wkhtmltopdf.exe')
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    pdf = pdfkit.from_string(html_full, False, configuration=config)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename={req.title.replace(' ', '_')}.pdf"
    })

