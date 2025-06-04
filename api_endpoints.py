import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from common import (
    AIResponse, 
    FlightRequest, 
    HotelRequest, 
    ItineraryRequest, 
    logger, 
    format_travel_data, 
    generate_itinerary, 
    get_ai_recommendation, 
    search_flights, 
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
async def get_hotel_recommendations(hotel_request: HotelRequest):
    """Search hotels and get AI recommendation."""
    try:
        # Fetch hotel data
        hotels = await search_booking_hotels(hotel_request)

        # Handle errors
        if isinstance(hotels, dict) and "error" in hotels:
            raise HTTPException(status_code=400, detail=hotels["error"])

        if not hotels:
            raise HTTPException(status_code=404, detail="No hotels found")

        # Format hotel data for AI
        hotels_text = format_travel_data("hotels", hotels)

        # Get AI recommendation
        ai_recommendation = await get_ai_recommendation("hotels", hotels_text)

        # Return response
        return AIResponse(
            hotels=hotels,
            ai_hotel_recommendation=ai_recommendation
        )
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status codes
        raise
    except Exception as e:
        logger.exception(f"Hotel search endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Hotel search error: {str(e)}")


@app.post("/complete_search/", response_model=AIResponse)
async def complete_travel_search(flight_request: FlightRequest, hotel_request: Optional[HotelRequest] = None):
    """Search for flights and hotels concurrently and get AI recommendations for both."""
    try:
        # If hotel request is not provided, create one from flight request
        if hotel_request is None:
            hotel_request = HotelRequest(
                location=flight_request.destination,
                check_in_date=flight_request.outbound_date,
                check_out_date=flight_request.return_date
            )

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

        # Format data for itinerary generation
        flights_text = format_travel_data("flights", flight_results.flights)
        hotels_text = format_travel_data("hotels", hotel_results.hotels)

        # Generate itinerary if both searches were successful
        itinerary = ""
        if flight_results.flights and hotel_results.hotels:
            itinerary = await generate_itinerary(
                destination=flight_request.destination,
                flights_text=flights_text,
                hotels_text=hotels_text,
                check_in_date=flight_request.outbound_date,
                check_out_date=flight_request.return_date
            )

        # Combine results
        return AIResponse(
            flights=flight_results.flights,
            hotels=hotel_results.hotels,
            ai_flight_recommendation=flight_results.ai_flight_recommendation,
            ai_hotel_recommendation=hotel_results.ai_hotel_recommendation,
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
    except Exception as e:
        logger.exception(f"Itinerary generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Itinerary generation error: {str(e)}")

