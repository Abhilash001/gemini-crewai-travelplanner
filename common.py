import os
import asyncio
import logging
from apify_client import ApifyClientAsync
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Optional
from serpapi import GoogleSearch
from crewai import Agent, Task, Crew, Process, LLM
from datetime import datetime
from functools import lru_cache
import re

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
SERP_API_KEY = os.getenv("SERP_API_KEY")
APIFY_API_KEY = os.getenv("APIFY_API_KEY")

# Initialize Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ==============================================
# 🤖 Initialize Google Gemini AI (LLM)
# ==============================================
@lru_cache(maxsize=1)
def initialize_llm():
    """Initialize and cache the LLM instance to avoid repeated initializations."""
    return LLM(
        model="gemini/gemini-2.0-flash",
        provider="google",
        api_key=GEMINI_API_KEY
    )

# ==============================================
# 📝 Pydantic Models
# ==============================================
class FlightRequest(BaseModel):
    origin: str
    destination: str
    outbound_date: str
    return_date: str


class HotelRequest(BaseModel):
    location: str
    check_in_date: str
    check_out_date: str


class ItineraryRequest(BaseModel):
    destination: str
    check_in_date: str
    check_out_date: str
    flights: str
    hotels: str


class FlightLeg(BaseModel):
    departure_airport: str
    departure_time: str
    arrival_airport: str
    arrival_time: str
    airline: str
    airline_logo: str
    travel_class: str
    flight_number: str
    duration: int


class LayoverInfo(BaseModel):
    airport: str
    airport_id: str
    duration: int
    overnight: Optional[bool] = False


class FlightInfo(BaseModel):
    airline: str
    price: int
    duration: int
    stops: str
    departure: str
    arrival: str
    travel_class: str
    return_date: str
    airline_logo: str
    legs: list[FlightLeg] = []
    layovers: list[LayoverInfo] = []
    return_flights: Optional[list] = []


class HotelInfo(BaseModel):
    name: str
    price: float
    rating: float
    location: str
    link: str

class HotelsGrouped(BaseModel):
    location: str
    check_in_date: str
    check_out_date: str
    hotels: List[HotelInfo] = []

class AIResponse(BaseModel):
    flights: List[FlightInfo] = []
    hotels: List[HotelInfo] = []
    hotels_grouped: List[HotelsGrouped] = []
    ai_flight_recommendation: str = ""
    ai_hotel_recommendations: Optional[List[str]] = []
    itinerary: str = ""


# ==============================================
# 🛫 Fetch Data from SerpAPI
# ==============================================
async def run_google_search(params):
    """Generic function to run SerpAPI searches asynchronously."""
    try:
        return await asyncio.to_thread(lambda: GoogleSearch(params).get_dict())
    except Exception as e:
        logger.exception(f"SerpAPI search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search API error: {str(e)}")


# ==============================================
# 🏨 Fetch Hotels from Booking.com
# ==============================================
async def run_apify_booking_search(params):
    if not APIFY_API_KEY:
        logger.error("APIFY_API_KEY environment variable is not set.")
        raise HTTPException(status_code=422, detail="APIFY API key is not configured.")
    try:
        apify_client = ApifyClientAsync(APIFY_API_KEY)

        # Start an Actor and wait for it to finish.
        actor_client = apify_client.actor('voyager/fast-booking-scraper')
        call_result = await actor_client.call(run_input=params)

        if call_result is None:
            logger.error(f"Actor run failed. Params: {params}")
            print('Actor run failed.')
            return []

        # Fetch results from the Actor run's default dataset.
        dataset_client = apify_client.dataset(call_result['defaultDatasetId'])
        list_items_result = await dataset_client.list_items()
        return list_items_result.items
    except Exception as e:
        logger.exception(f"Apify Client error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Apify Client error: {str(e)}")


async def search_flights(flight_request: FlightRequest):
    """Fetch real-time flight details from Google Flights using SerpAPI."""
    logger.info(f"Searching flights: {flight_request.origin} to {flight_request.destination}")

    params = {
        "api_key": SERP_API_KEY,
        "engine": "google_flights",
        "hl": "en",
        "gl": "in",
        "departure_id": flight_request.origin.strip().upper(),
        "arrival_id": flight_request.destination.strip().upper(),
        "outbound_date": flight_request.outbound_date,
        "return_date": flight_request.return_date,
        "currency": "INR"
    }

    search_results = await run_google_search(params)

    if "error" in search_results:
        logger.error(f"Flight search error: {search_results['error']}")
        return {"error": search_results["error"]}

    best_flights = search_results.get("best_flights", [])
    if not best_flights:
        logger.warning("No flights found in search results")
        return []

    formatted_flights = []
    for flight in best_flights:
        if not flight.get("flights") or len(flight["flights"]) == 0:
            continue

        # Build legs (departure)
        legs = []
        for leg in flight["flights"]:
            legs.append({
                "departure_airport": f"{leg.get('departure_airport', {}).get('name', 'Unknown')} ({leg.get('departure_airport', {}).get('id', '???')})",
                "departure_time": leg.get('departure_airport', {}).get('time', 'N/A'),
                "arrival_airport": f"{leg.get('arrival_airport', {}).get('name', 'Unknown')} ({leg.get('arrival_airport', {}).get('id', '???')})",
                "arrival_time": leg.get('arrival_airport', {}).get('time', 'N/A'),
                "airline": leg.get("airline", "Unknown Airline"),
                "airline_logo": leg.get("airline_logo", ""),
                "travel_class": leg.get("travel_class", "Economy"),
                "flight_number": leg.get("flight_number", ""),
                "duration": int(leg.get("duration", 0))
            })

        # Build layovers (departure)
        layovers = []
        for lay in flight.get("layovers", []):
            layovers.append({
                "airport": lay.get("name", ""),
                "airport_id": lay.get("id", ""),
                "duration": int(lay.get("duration", 0)),
                "overnight": lay.get("overnight", False)
            })

        first_leg = flight["flights"][0]
        last_leg = flight["flights"][-1]

        # --- Fetch return flights using departure_token ---
        return_flights = []
        departure_token = flight.get("departure_token")
        if departure_token:
            return_params = {
                "api_key": SERP_API_KEY,
                "engine": "google_flights",
                "hl": "en",
                "gl": "in",
                "departure_id": flight_request.origin.strip().upper(),
                "arrival_id": flight_request.destination.strip().upper(),
                "outbound_date": flight_request.outbound_date,
                "return_date": flight_request.return_date,
                "currency": "INR",
                "departure_token": departure_token
            }
            try:
                return_results = await run_google_search(return_params)
                return_top_flights = return_results.get("best_flights", [])
                if not return_top_flights:
                    return_top_flights = return_results.get("other_flights", [])
                    return_top_flights = return_top_flights[:min(3, len(return_top_flights))]  # Limit to 3 other flights
                for ret_flight in return_top_flights:
                    ret_legs = []
                    for leg in ret_flight["flights"]:
                        ret_legs.append({
                            "departure_airport": f"{leg.get('departure_airport', {}).get('name', 'Unknown')} ({leg.get('departure_airport', {}).get('id', '???')})",
                            "departure_time": leg.get('departure_airport', {}).get('time', 'N/A'),
                            "arrival_airport": f"{leg.get('arrival_airport', {}).get('name', 'Unknown')} ({leg.get('arrival_airport', {}).get('id', '???')})",
                            "arrival_time": leg.get('arrival_airport', {}).get('time', 'N/A'),
                            "airline": leg.get("airline", "Unknown Airline"),
                            "airline_logo": leg.get("airline_logo", ""),
                            "travel_class": leg.get("travel_class", "Economy"),
                            "flight_number": leg.get("flight_number", ""),
                            "duration": int(leg.get("duration", 0))
                        })
                    return_flights.append({
                        "airline": ret_flight["flights"][0].get("airline", "Unknown Airline"),
                        "price": int(ret_flight.get("price", 0)),
                        "duration": int(ret_flight.get("total_duration", 0)),
                        "stops": "Nonstop" if len(ret_flight["flights"]) == 1 else f"{len(ret_flight['flights']) - 1} stop(s)",
                        "departure": f"{ret_flight['flights'][0].get('departure_airport', {}).get('name', 'Unknown')} ({ret_flight['flights'][0].get('departure_airport', {}).get('id', '???')}) at {ret_flight['flights'][0].get('departure_airport', {}).get('time', 'N/A')}",
                        "arrival": f"{ret_flight['flights'][-1].get('arrival_airport', {}).get('name', 'Unknown')} ({ret_flight['flights'][-1].get('arrival_airport', {}).get('id', '???')}) at {ret_flight['flights'][-1].get('arrival_airport', {}).get('time', 'N/A')}",
                        "travel_class": ret_flight["flights"][0].get("travel_class", "Economy"),
                        "airline_logo": ret_flight["flights"][0].get("airline_logo", ""),
                        "legs": ret_legs,
                        "layovers": [
                            {
                                "airport": lay.get("name", ""),
                                "airport_id": lay.get("id", ""),
                                "duration": int(lay.get("duration", 0)),
                                "overnight": lay.get("overnight", False)
                            } for lay in ret_flight.get("layovers", [])
                        ]
                    })
            except Exception as e:
                logger.warning(f"Error fetching return flights: {str(e)}")

        formatted_flights.append(FlightInfo(
            airline=first_leg.get("airline", "Unknown Airline"),
            price=int(flight.get("price", 0)),
            duration=int(flight.get("total_duration", 0)),
            stops="Nonstop" if len(flight["flights"]) == 1 else f"{len(flight['flights']) - 1} stop(s)",
            departure=f"{first_leg.get('departure_airport', {}).get('name', 'Unknown')} ({first_leg.get('departure_airport', {}).get('id', '???')}) at {first_leg.get('departure_airport', {}).get('time', 'N/A')}",
            arrival=f"{last_leg.get('arrival_airport', {}).get('name', 'Unknown')} ({last_leg.get('arrival_airport', {}).get('id', '???')}) at {last_leg.get('arrival_airport', {}).get('time', 'N/A')}",
            travel_class=first_leg.get("travel_class", "Economy"),
            return_date=flight_request.return_date,
            airline_logo=first_leg.get("airline_logo", ""),
            legs=legs,
            layovers=layovers,
            return_flights=return_flights  # Attach return flights here
        ))

    logger.info(f"Found {len(formatted_flights)} flights")
    return formatted_flights


async def search_google_hotels(hotel_request: HotelRequest):
    """Fetch hotel information from SerpAPI."""
    logger.info(f"Searching hotels for: {hotel_request.location}")

    params = {
        "api_key": SERP_API_KEY,
        "engine": "google_hotels",
        "q": hotel_request.location,
        "hl": "en",
        "gl": "in",
        "check_in_date": hotel_request.check_in_date,
        "check_out_date": hotel_request.check_out_date,
        "currency": "INR",
        "sort_by": 3,
        "rating": 8,
        "property_types": 14
    }

    search_results = await run_google_search(params)

    if "error" in search_results:
        logger.error(f"Hotel search error: {search_results['error']}")
        return {"error": search_results["error"]}

    hotel_properties = search_results.get("properties", [])
    if not hotel_properties:
        logger.warning("No hotels found in search results")
        return []

    formatted_hotels = []
    for hotel in hotel_properties:
        try:
            formatted_hotels.append(HotelInfo(
                name=hotel.get("name", "Unknown Hotel"),
                price=float(hotel.get("rate_per_night", {}).get("extracted_lowest", 0.0)),
                rating=float(hotel.get("overall_rating", 0.0)),
                location=hotel.get("location", "N/A"),
                link=hotel.get("link", "N/A")
            ))
        except Exception as e:
            logger.warning(f"Error formatting hotel data: {str(e)}")
            # Continue with next hotel rather than failing completely

    logger.info(f"Found {len(formatted_hotels)} hotels")
    return formatted_hotels


async def search_booking_hotels(hotel_request: HotelRequest):
    """Fetch hotel information from Apify - Booking.com."""
    logger.info(f"Searching hotels for: {hotel_request.location}")

    check_in_date = datetime.strptime(hotel_request.check_in_date, "%Y-%m-%d")
    check_out_date = datetime.strptime(hotel_request.check_out_date, "%Y-%m-%d")
    date_diff = check_out_date - check_in_date

    if date_diff.days <= 0:
        logger.error("Check out date is less than or equal to check in date")
        return []

    params = {
        "search": hotel_request.location,
        "maxItems": 5,
        "propertyType": "Hostels",
        "sortBy": "distance_from_search",
        "minScore": "8",
        "starsCountFilter": "any",
        "currency": "INR",
        "language": "en-gb",
        "checkIn": hotel_request.check_in_date,
        "checkOut": hotel_request.check_out_date,
        "rooms": 1,
        "adults": 1,
        "children": 0,
        "minMaxPrice": "0-999999"
    }

    hotel_results = await run_apify_booking_search(params)

    if not hotel_results:
        logger.warning("No hotels found in search results")
        return []

    formatted_hotels = []
    for hotel in hotel_results:
        try:
            formatted_hotels.append(HotelInfo(
                name=hotel.get("name", "Unknown Hotel"),
                price=round(float(hotel.get("price", 0.0)) / date_diff.days),
                rating=float(hotel.get("rating", 0.0)),
                location=hotel.get("address", "N/A"),
                link=hotel.get("url", "N/A")
            ))
        except Exception as e:
            logger.warning(f"Error formatting hotel data: {str(e)}")
            # Continue with next hotel rather than failing completely

    logger.info(f"Found {len(formatted_hotels)} hotels")
    return formatted_hotels


# ==============================================
# 🔄 Format Data for AI
# ==============================================
def format_travel_data(data_type, data):
    """Generic formatter for both flight and hotel data."""
    if not data:
        return f"No {data_type} available."

    if data_type == "flights":
        formatted_text = "✈️ **Available round-trip flight options**:\n\n"
        for i, flight in enumerate(data):
            formatted_text += (
                f"**Departure Flight {i + 1}:**\n"
                f"✈️ **Airline:** {flight.airline}\n"
                f"💰 **Price:** ₹{flight.price}\n"
                f"⏱️ **Duration:** {flight.duration}\n"
                f"🛑 **Stops:** {flight.stops}\n"
                f"🕔 **Departure:** {flight.departure}\n"
                f"🕖 **Arrival:** {flight.arrival}\n"
                f"💺 **Class:** {flight.travel_class}\n"
            )
            # List return flights for this departure
            if flight.return_flights:
                for j, ret in enumerate(flight.return_flights):
                    formatted_text += (
                        f"\n  ↩️ **Return Flight {j + 1}:**\n"
                        f"  ✈️ **Airline:** {ret['airline']}\n"
                        f"  💰 **Price:** ₹{ret['price']}\n"
                        f"  ⏱️ **Duration:** {ret['duration']}\n"
                        f"  🛑 **Stops:** {ret['stops']}\n"
                        f"  🕔 **Departure:** {ret['departure']}\n"
                        f"  🕖 **Arrival:** {ret['arrival']}\n"
                        f"  💺 **Class:** {ret['travel_class']}\n"
                    )
            formatted_text += "\n"
    elif data_type == "hotels":
        formatted_text = "🏨 **Available Hotel Options**:\n\n"
        for i, item in enumerate(data):
            # Support both old and new format for backward compatibility
            if isinstance(item, dict) and "hotel" in item:
                hotel = item["hotel"]
                check_in = item.get("check_in", "N/A")
                check_out = item.get("check_out", "N/A")
                location = item.get("location", "N/A")
            else:
                hotel = item
                check_in = check_out = location = "N/A"
            formatted_text += (
                f"**Hotel {i + 1}:**\n"
                f"🏨 **Name:** {hotel.name}\n"
                f"💰 **Price:** ₹{hotel.price}\n"
                f"⭐ **Rating:** {hotel.rating}\n"
                f"📍 **Location:** {hotel.location if location == 'N/A' else location}\n"
                f"🗓️ **Check-in:** {check_in}\n"
                f"🗓️ **Check-out:** {check_out}\n"
                f"🔗 **More Info:** [Link]({hotel.link})\n\n"
            )
    else:
        return "Invalid data type."

    return formatted_text.strip()


# ==============================================
# 🧠 AI Analysis Functions
# ==============================================
async def get_ai_recommendation(data_type, formatted_data):
    """Unified function for getting AI recommendations for both flights and hotels."""
    logger.info(f"Getting {data_type} analysis from AI")
    llm_model = initialize_llm()

    # Configure agent based on data type
    if data_type == "flights":
        role = "AI Flight Analyst"
        goal = "Analyze round-trip flight options and recommend the best combination considering price, duration, stops, and overall convenience for both departure and return flights."
        backstory = f"AI expert that provides in-depth analysis comparing round-trip flight options based on multiple factors."
        description = """
        Recommend the best round-trip flight combination from the available options, based on the details provided below.

        **At the start of your response, clearly state the recommended departure flight in the format:**
        `Recommended Departure Flight: <number>`
        **For the selected departure flight, clearly state the recommended return flight in the next line in the format:**
        `Recommended Return Flight: <number>`

        **Reasoning for Recommendation:**
        - **💰 Price:** Explain why this round-trip offers the best value.
        - **⏱️ Duration:** Explain why the total travel time is optimal.
        - **🛑 Stops:** Discuss the convenience of stops for both legs.
        - **💺 Travel Class:** Describe comfort and amenities for both flights.

        **Format Requirements**:
        - Use markdown formatting

        Use the provided round-trip flight data as the basis for your recommendation. Be sure to justify your choice using clear reasoning for both departure and return flights. Do not repeat the flight details in your response.
        """
    elif data_type == "hotels":
        role = "AI Hotel Analyst"
        goal = "Analyze hotel options and recommend the best one considering price, rating, location, and amenities."
        backstory = f"AI expert that provides in-depth analysis comparing hotel options based on multiple factors."
        description = """
        Based on the following analysis, generate a detailed recommendation for the best hotel. Your response should include clear reasoning based on price, rating, location, and amenities.

        **At the start of your response, clearly state the recommended hotel in the format:**
        `Recommended Hotel: <number>`

        **🏆 AI Hotel Recommendation**
        We recommend the best hotel based on the following analysis:

        **Reasoning for Recommendation**:
        - **💰 Price:** The recommended hotel is the best option for the price compared to others, offering the best value for the amenities and services provided.
        - **⭐ Rating:** With a higher rating compared to the alternatives, it ensures a better overall guest experience. Explain why this makes it the best choice.
        - **📍 Location:** The hotel is in a prime location, close to important attractions, making it convenient for travelers.
        - **🛋️ Amenities:** The hotel offers amenities like Wi-Fi, pool, fitness center, free breakfast, etc. Discuss how these amenities enhance the experience, making it suitable for different types of travelers.

        📝 **Reasoning Requirements**:
        - Ensure that each section clearly explains why this hotel is the best option based on the factors of price, rating, location, and amenities.
        - Compare it against the other options and explain why this one stands out.
        - Provide concise, well-structured reasoning to make the recommendation clear to the traveler.
        - Your recommendation should help a traveler make an informed decision based on multiple factors, not just one.

        **Format Requirements**:
        - Use markdown formatting
        """
    else:
        raise ValueError("Invalid data type for AI recommendation")

    # Create the agent and task
    analyze_agent = Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        llm=llm_model,
        verbose=False
    )

    analyze_task = Task(
        description=f"{description}\n\nData to analyze:\n{formatted_data}",
        agent=analyze_agent,
        expected_output=f"A structured recommendation explaining the best {data_type} choice based on the analysis of provided details."
    )

    analyst_crew = Crew(
        agents=[analyze_agent],
        tasks=[analyze_task],
        process=Process.sequential,
        verbose=False
    )

    try:
        # Run the CrewAI analysis in a thread pool
        crew_results = await asyncio.to_thread(analyst_crew.kickoff)

        # Handle different possible return types from CrewAI
        if hasattr(crew_results, 'outputs') and crew_results.outputs:
            return crew_results.outputs[0]
        elif hasattr(crew_results, 'get'):
            return crew_results.get(role, f"No {data_type} recommendation available.")
        else:
            return str(crew_results)
    except Exception as e:
        logger.exception(f"Error in AI {data_type} analysis: {str(e)}")
        return f"Unable to generate {data_type} recommendation due to an error."


async def generate_itinerary(destination, flights_text, hotels_text, check_in_date, check_out_date):
    """Generate a detailed travel itinerary based on flight and hotel information."""
    try:
        # Convert the string dates to datetime objects
        check_in = datetime.strptime(check_in_date, "%Y-%m-%d")
        check_out = datetime.strptime(check_out_date, "%Y-%m-%d")

        # Calculate the difference in days
        days = (check_out - check_in).days

        llm_model = initialize_llm()

        analyze_agent = Agent(
            role="AI Travel Planner",
            goal="Create a detailed itinerary for the user based on flight and hotel information",
            backstory="AI travel expert generating a day-by-day itinerary including flight details, hotel stays, and must-visit locations in the destination.",
            llm=llm_model,
            verbose=False
        )

        analyze_task = Task(
            description=f"""
            Based on the following details, create a {days}-day itinerary for the user:

            **Flight Details**:
            {flights_text}

            **Hotel Details**:
            {hotels_text}

            **Destination**: {destination}

            **Travel Dates**: {check_in_date} to {check_out_date} ({days} days)

            The itinerary should include:
            - Flight arrival and departure information
            - Hotel check-in and check-out details
            - Day-by-day breakdown of activities
            - Must-visit attractions and estimated visit times
            - Restaurant recommendations for meals
            - Tips for local transportation

            📝 **Format Requirements**:
            - Use markdown formatting with clear headings (# for main headings, ## for days, ### for sections)
            - Include emojis for different types of activities (🏛️ for landmarks, 🍽️ for restaurants, etc.)
            - Use bullet points for listing activities
            - Include estimated timings for each activity
            - Format the itinerary to be visually appealing and easy to read
            """,
            agent=analyze_agent,
            expected_output="A well-structured, visually appealing itinerary in markdown format, including flight, hotel, and day-wise breakdown with emojis, headers, and bullet points."
        )

        itinerary_planner_crew = Crew(
            agents=[analyze_agent],
            tasks=[analyze_task],
            process=Process.sequential,
            verbose=False
        )

        crew_results = await asyncio.to_thread(itinerary_planner_crew.kickoff)

        # Handle different possible return types from CrewAI
        if hasattr(crew_results, 'outputs') and crew_results.outputs:
            return crew_results.outputs[0]
        elif hasattr(crew_results, 'get'):
            return crew_results.get("AI Travel Planner", "No itinerary available.")
        else:
            return str(crew_results)

    except Exception as e:
        logger.exception(f"Error generating itinerary: {str(e)}")
        return "Unable to generate itinerary due to an error. Please try again later."


# After getting the itinerary string from the LLM
def strip_code_fence(md: str) -> str:
    return re.sub(r'^```(?:markdown)?\s*([\s\S]*?)```$', r'\1', md.strip(), flags=re.MULTILINE)

def extract_recommended_hotel_index(recommendation_text):
    """
    Extracts the recommended option index from the AI recommendation text.
    Looks for lines like 'Recommended Option: 2' or 'Recommended Hotel: 1'.
    Returns a zero-based index, or 0 if not found.
    """
    pattern = r"Recommended Hotel:\s*(\d+)"
    match = re.search(pattern, recommendation_text, re.IGNORECASE)
    if match:
        return int(match.group(1)) - 1
    return 0

def extract_recommended_flight_indices(recommendation_text):
    """
    Extracts the recommended departure and return flight indices from the AI recommendation text.
    Returns (departure_index, return_index), both zero-based. If not found, defaults to 0.
    """
    dep_match = re.search(r"Recommended Departure Flight:\s*(\d+)", recommendation_text, re.IGNORECASE)
    ret_match = re.search(r"Recommended Return Flight:\s*(\d+)", recommendation_text, re.IGNORECASE)
    dep_idx = int(dep_match.group(1)) - 1 if dep_match else 0
    ret_idx = int(ret_match.group(1)) - 1 if ret_match else 0
    return dep_idx, ret_idx

def format_selected_travel_data(data_type, data):
    """Format only the selected flight(s) or hotel(s) for itinerary generation."""
    if not data:
        return f"No {data_type} selected."

    if data_type == "flights":
        flight = data[0]
        text = (
            f"✈️ **Selected Departure Flight**\n"
            f"- Airline: {flight.airline}\n"
            f"- Duration: {flight.duration}\n"
            f"- Stops: {flight.stops}\n"
            f"- Departure: {flight.departure}\n"
            f"- Arrival: {flight.arrival}\n"
            f"- Class: {flight.travel_class}\n"
        )
        ret = flight.return_flights[0]
        text += (
            f"\n↩️ **Selected Return Flight**\n"
            f"- Airline: {ret['airline']}\n"
            f"- Duration: {ret['duration']}\n"
            f"- Stops: {ret['stops']}\n"
            f"- Departure: {ret['departure']}\n"
            f"- Arrival: {ret['arrival']}\n"
            f"- Class: {ret['travel_class']}\n"
        )
        text += (f"Total round-trip Price:  ₹{ret['price'] if ret['price'] > 0 else flight.price}\n")
        return text.strip()

    elif data_type == "hotels":
        text = ""
        for i, item in enumerate(data):
            if isinstance(item, dict) and "hotel" in item:
                hotel = item["hotel"]
                check_in = item.get("check_in", "N/A")
                check_out = item.get("check_out", "N/A")
                location = item.get("location", "N/A")
            else:
                hotel = item
                check_in = check_out = location = "N/A"
            text += (
                f"🏨 **Selected Hotel {i+1}**\n"
                f"- Name: {hotel.name}\n"
                f"- Price: ₹{hotel.price} per night\n"
                f"- Rating: {hotel.rating}\n"
                f"- Location: {hotel.location if location == 'N/A' else location}\n"
                f"- Check-in: {check_in}\n"
                f"- Check-out: {check_out}\n"
                f"- More Info: {hotel.link}\n\n"
            )
        return text.strip()
    else:
        return "Invalid data type."

