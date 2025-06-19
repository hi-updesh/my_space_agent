# Import necessary libraries
import os
import requests # to make requests to web APIs: RocketLaunch.Live and OpenWeatherMap
import datetime # for handling dates and times
from zoneinfo import ZoneInfo # for timezone information
from dotenv import load_dotenv 
from google.adk.agents import Agent # The core Google ADK Agent class
from typing import Optional, Any # for more flexible type hinting
from google import genai 
import re # for better parsing

# --- Global variable for tracking tool calls for evaluation purposes ---
# This is a simple list to store the names of tools as they are called.
# In a real-world scenario, might want a more sophisticated logging mechanism
# like storing arguments, timestamps, or using a dedicated logging library.
TOOL_CALL_LOG = []

def clear_tool_log():
    """Clears the tool call log for a new evaluation run."""
    global TOOL_CALL_LOG
    TOOL_CALL_LOG = []

def get_tool_log():
    """Returns the current tool call log."""
    return TOOL_CALL_LOG

# --- Load Environment Variables ---
load_dotenv()

# --- API Keys and Base URLs ---
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

ROCKETLAUNCHLIVE_API_BASE_URL = "https://fdo.rocketlaunch.live/json"
SPACEX_API_BASE_URL = "https://api.spacexdata.com/v4" # Keep for launchpad details if needed

# --- Tool Functions (Our "Specialized Helpers") ---

def get_spacex_launch() -> dict:
    """
    Retrieves information about the next upcoming SpaceX launch using RocketLaunch.Live's FREE access API.
    This function acts as our first "helper" to get the initial data.
    It now prioritizes the *first* SpaceX launch found in the next 5, then falls back to historical
    if no SpaceX launches are found in the initial list.
    It also ensures best effort to get launchpad coordinates or a general location name.
    """
    global TOOL_CALL_LOG
    TOOL_CALL_LOG.append("get_spacex_launch")
    print("Calling RocketLaunch.Live FREE ACCESS API to get the next 5 launches...")
    
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    # Default status. Will be updated based on the launch found or fallback.
    data_freshness_status = "unknown" 

    def parse_rll_date(date_val: Any) -> Optional[datetime.datetime]: # Accepts Any type now
        """Helper to parse RocketLaunch.Live API date strings or timestamps into timezone-aware datetime objects."""
        if isinstance(date_val, str):
            try:
                # Attempt ISO 8601 parsing (e.g., "2025-06-19T03:00Z")
                return datetime.datetime.fromisoformat(date_val.replace('Z', '+00:00'))
            except ValueError:
                # If not ISO 8601, try to interpret as a string-encoded Unix timestamp (e.g., "1750377596")
                try:
                    return datetime.datetime.fromtimestamp(int(date_val), tz=datetime.timezone.utc)
                except (ValueError, TypeError):
                    pass # Not an ISO string, not a string-encoded integer, fall through
        elif isinstance(date_val, (int, float)):
            try:
                # Attempt Unix timestamp parsing (already an int/float)
                return datetime.datetime.fromtimestamp(date_val, tz=datetime.timezone.utc)
            except ValueError:
                pass # Fall through
        return None

    try:
        # Use the FREE access endpoint for the next 5 launches
        response = requests.get(f"{ROCKETLAUNCHLIVE_API_BASE_URL}/launches/next/5")
        response.raise_for_status()
        rll_data = response.json()

        launches = rll_data.get("result", [])
        
        found_spacex_in_next_5 = False
        launch_data = None # hold the chosen launch data

        # Iterate to find the *first* SpaceX launch in the list
        for l in launches:
            if l.get("provider", {}).get("name", "").lower() == "spacex":
                launch_data = l
                found_spacex_in_next_5 = True
                
                # Check if this found SpaceX launch is actually in the future
                # Prioritize win_open, then t0, then sort_date for the most accurate future check from RLL
                launch_time_obj = parse_rll_date(launch_data.get("win_open")) or \
                                  parse_rll_date(launch_data.get("t0")) or \
                                  parse_rll_date(launch_data.get("sort_date")) # handles Unix timestamp 
                
                if launch_time_obj and launch_time_obj > current_time_utc:
                    data_freshness_status = "future"
                    print(f"Found next upcoming SpaceX launch from RocketLaunch.Live FREE (future): {launch_data.get('name')}")
                else:
                    # If it's SpaceX but not strictly in the future (based on parsed dates)
                    # or if the date couldn't be parsed as future.
                    data_freshness_status = "found_but_not_future" 
                    print(f"Found first SpaceX launch from RocketLaunch.Live FREE (not strictly future/parsed or past): {launch_data.get('name')}")
                break # Take the first instance found

        if not found_spacex_in_next_5:
            # If no SpaceX launch was found in the initial 'next 5' from RocketLaunch.Live
            print("None out of the next 5 global rocket launches is from SpaceX. Falling back to latest successful past launch from original SpaceX API.")
            data_freshness_status = "no_spacex_in_next_5_fallback" # Specific status for this scenario
            
            response_past = requests.get(f"{SPACEX_API_BASE_URL}/launches/past")
            response_past.raise_for_status()
            past_launches_data = response_past.json()

            spacex_successful_past = [l for l in past_launches_data if l.get("success") == True]
            
            if spacex_successful_past:
                # Sort by date_utc descending to get the most recent successful past launch
                spacex_successful_past.sort(key=lambda x: parse_spacex_date_old_api(x.get("date_utc")) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), reverse=True)
                launch_data = spacex_successful_past[0]
                print(f"Using latest successful past launch from old SpaceX API: {launch_data.get('name')}")
            else:
                # If no SpaceX launches found after all attempts
                return {"status": "error", "error_message": "No upcoming or successful past SpaceX launches found from any source after all attempts."}

        # If launch_data is still None at this point, it means an unexpected error occurred
        if launch_data is None:
             return {"status": "error", "error_message": "Failed to retrieve any SpaceX launch data after all attempts."}


        # Extract relevant information and build location_info
        launch_name = launch_data.get("name", "Unknown Launch")
        details = launch_data.get("launch_description", launch_data.get("details", "No details available."))
        
        # --- Robust Date Extraction Logic for launch_date_utc string ---
        # This will be the ISO-formatted date string that the LLM receives.
        # The LLM's instruction will then guide how it formats this for the user.
        launch_date_utc_str = None
        current_year = datetime.datetime.now(datetime.timezone.utc).year # Get current year for heuristics

        # Priority 1: win_open or t0 (direct ISO strings from RLL)
        if launch_data.get("win_open"):
            launch_date_utc_str = launch_data["win_open"]
        elif launch_data.get("t0"):
            launch_date_utc_str = launch_data["t0"]

        # Priority 2: sort_date (Unix timestamp from RLL, convert to ISO)
        if not launch_date_utc_str and launch_data.get("sort_date") is not None:
            parsed_dt = parse_rll_date(launch_data["sort_date"])
            if parsed_dt:
                launch_date_utc_str = parsed_dt.isoformat().replace('+00:00', 'Z')

        # Priority 3: est_date (structured object from RLL, reconstruct date)
        if not launch_date_utc_str and launch_data.get("est_date"):
            est_date = launch_data["est_date"]
            year = est_date.get("year", current_year) # Use current year as fallback if not present
            month = est_date.get("month")
            day = est_date.get("day")
            if year and month and day:
                try:
                    dt_obj = datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)
                    launch_date_utc_str = dt_obj.isoformat().replace('+00:00', 'Z')
                except (TypeError, ValueError):
                    pass # Failed to construct from est_date

        # Priority 4: launch_description (regex extract "Month Day, Year")
        if not launch_date_utc_str and launch_data.get("launch_description"):
            # Example: "A SpaceX Falcon 9 rocket will launch the Ax-4 mission. The launch date is currently targeted for June 19, 2025 (UTC)."
            match = re.search(r'(?:on|for)\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})(?:\s*\(UTC\))?', launch_data["launch_description"])
            if match:
                try:
                    date_part = match.group(1) # e.g., "June 19, 2025"
                    dt_obj = datetime.datetime.strptime(date_part, "%B %d, %Y").replace(tzinfo=datetime.timezone.utc)
                    launch_date_utc_str = dt_obj.isoformat().replace('+00:00', 'Z')
                except ValueError:
                    pass

        # Priority 5: quicktext (regex extract "Mon Day", add year heuristic)
        if not launch_date_utc_str and launch_data.get("quicktext"):
            # Example: "Falcon 9 - Ax-4 - Jun 19 (estimated)"
            match = re.search(r'([A-Za-z]{3}\s+\d{1,2})', launch_data["quicktext"])
            if match:
                date_part = match.group(1) # e.g., "Jun 19"
                try:
                    # Attempt with current year, then check if it's in the past and adjust to next year
                    dt_obj = datetime.datetime.strptime(f"{date_part}, {current_year}", "%b %d, %Y").replace(tzinfo=datetime.timezone.utc)
                    # Adjust year if the date is in the past, accounting for the current month
                    if dt_obj < current_time_utc - datetime.timedelta(days=7) and dt_obj.month <= current_time_utc.month:
                        dt_obj = datetime.datetime.strptime(f"{date_part}, {current_year + 1}", "%b %d, %Y").replace(tzinfo=datetime.timezone.utc)
                    launch_date_utc_str = dt_obj.isoformat().replace('+00:00', 'Z')
                except ValueError:
                    pass # Couldn't parse date_part

        # Priority 6: date_str (simple "Mon Day" or "Mon Day, Year", add year heuristic if needed)
        if not launch_date_utc_str and launch_data.get("date_str"):
            date_part = launch_data["date_str"]
            # Check if date_str already includes a year
            if re.search(r'\d{4}', date_part): # "Jun 19, 2025"
                try:
                    dt_obj = datetime.datetime.strptime(date_part, "%b %d, %Y").replace(tzinfo=datetime.timezone.utc)
                    launch_date_utc_str = dt_obj.isoformat().replace('+00:00', 'Z')
                except ValueError:
                    pass
            else: # Assume "Jun 19" format
                try:
                    dt_obj = datetime.datetime.strptime(f"{date_part}, {current_year}", "%b %d, %Y").replace(tzinfo=datetime.timezone.utc)
                    # Adjust year as in quicktext
                    if dt_obj < current_time_utc - datetime.timedelta(days=7) and dt_obj.month <= current_time_utc.month:
                        dt_obj = datetime.datetime.strptime(f"{date_part}, {current_year + 1}", "%b %d, %Y").replace(tzinfo=datetime.timezone.utc)
                    launch_date_utc_str = dt_obj.isoformat().replace('+00:00', 'Z')
                except ValueError:
                    pass # Couldn't parse date_part

        # Final fallback for launch_date_utc (for the output dict)
        if launch_date_utc_str is None:
            # If the launch_data came from the old SpaceX API fallback, use its date_utc directly
            if data_freshness_status == "past_fallback" and launch_data.get("date_utc"):
                launch_date_utc_str = launch_data.get("date_utc")
            else:
                launch_date_utc_str = "Unknown Date" # Last resort if no date could be parsed

        launch_date_utc = launch_date_utc_str
        # --- End Robust Date Extraction Logic ---

        location_info = {
            "name": "Unknown Launchpad",
            "latitude": None,
            "longitude": None,
            "region": "",
            "locality": ""
        }

        # Try to get location info from RLL data (from 'pad' object)
        if launch_data.get("pad"):
            location_info["name"] = launch_data["pad"].get("name", "Unknown Launchpad")
            location_info["latitude"] = launch_data["pad"].get("latitude")
            location_info["longitude"] = launch_data["pad"].get("longitude")
            if launch_data["pad"].get("location"):
                location_info["region"] = launch_data["pad"]["location"].get("state_name", "")
                # RLL's pad.location.name is often the locality (e.g., "Vandenberg SFB")
                location_info["locality"] = launch_data["pad"]["location"].get("name", "") 
        
        # If location info is still missing from RLL, try old SpaceX API's launchpad details
        # This uses the original SpaceX API's launchpad ID (UUID) if available from its data.
        if (not location_info["latitude"] or not location_info["longitude"]) and launch_data.get("launchpad"):
            print("Attempting to get missing launchpad lat/lon from old SpaceX API using its launchpad ID.")
            old_spacex_launchpad_details = get_launchpad_details_from_spacex_api(launch_data.get("launchpad"))
            if old_spacex_launchpad_details["status"] == "success":
                location_info["latitude"] = old_spacex_launchpad_details["data"].get("latitude")
                location_info["longitude"] = old_spacex_launchpad_details["data"].get("longitude")
                # Also update name if old API has a better one
                if "Unknown Launchpad" in location_info["name"]:
                    location_info["name"] = old_spacex_launchpad_details["data"].get("name")
                if not location_info["region"]:
                    location_info["region"] = old_spacex_launchpad_details["data"].get("region", "")
                if not location_info["locality"]:
                    location_info["locality"] = old_spacex_launchpad_details["data"].get("locality", "")

        # --- Construct a robust display_name for geocoding fallback ---
        location_parts = []
        # Prioritize the launchpad's specific geographic name (e.g., "Vandenberg SFB")
        if location_info.get("locality"): # This is often pad.location.name from RLL
            location_parts.append(location_info["locality"])
        elif location_info.get("name") and "Unknown Launchpad" not in location_info["name"]:
            location_parts.append(location_info["name"])

        # Add region (e.g., "Florida") and country for better specificity in geocoding
        if location_info.get("region"):
            location_parts.append(location_info["region"])
        # Ensure 'country' from the provided JSON is used if available (from RLL data)
        if launch_data.get("pad", {}).get("location", {}).get("country"):
            location_parts.append(launch_data["pad"]["location"]["country"])


        # Create the combined display name, or a generic string if nothing works
        location_info["display_name"] = ", ".join(filter(None, location_parts)) or "the launch area"
        print(f"Constructed display_name for geocoding: '{location_info['display_name']}'")
        # --- End display_name construction ---


        launch_info = {
            "name": launch_name,
            "date_utc": launch_date_utc,
            "details": details,
            "location_info": location_info, 
            "data_freshness_status": data_freshness_status # Pass the determined status
        }
        
        return {"status": "success", "data": launch_info}

    except requests.exceptions.RequestException as e:
        return {"status": "error", "error_message": f"Failed to fetch SpaceX launch data from RocketLaunch.Live FREE API: {e}. Please check network."}
    except Exception as e:
        return {"status": "error", "error_message": f"An unexpected error occurred while fetching RocketLaunch.Live FREE data: {e}. Please check the code."}

# A separate helper to parse dates from the old SpaceX API if needed for fallback
def parse_spacex_date_old_api(date_str: Optional[str]) -> Optional[datetime.datetime]:
    """Helper to parse original SpaceX API date strings for fallback logic."""
    if not date_str:
        return None
    try:
        return datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        return None

# A separate helper to get launchpad details from the old SpaceX API if needed
def get_launchpad_details_from_spacex_api(launchpad_id: str) -> dict:
    """
    Retrieves detailed information about a SpaceX launchpad using the original SpaceX API.
    This is a fallback helper for launchpad details if RocketLaunch.Live doesn't provide full coordinates.
    """
    global TOOL_CALL_LOG
    TOOL_CALL_LOG.append(f"get_launchpad_details_from_spacex_api({launchpad_id})")
    print(f"Calling OLD SpaceX API to get launchpad details for ID: {launchpad_id}")
    try:
        response = requests.get(f"{SPACEX_API_BASE_URL}/launchpads/{launchpad_id}")
        response.raise_for_status()
        launchpad_data = response.json()

        location = launchpad_data.get("full_name")
        latitude = launchpad_data.get("latitude")
        longitude = launchpad_data.get("longitude")
        region = launchpad_data.get("region")
        locality = launchpad_data.get("locality")

        return {
            "status": "success",
            "data": {
                "name": location,
                "latitude": latitude,
                "longitude": longitude,
                "region": region,
                "locality": locality
            }
        }
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error_message": f"Failed to fetch launchpad details from old SpaceX API: {e}"}
    except Exception as e:
        return {"status": "error", "error_message": f"An unexpected error occurred fetching old SpaceX launchpad details: {e}"}

def get_coordinates_from_name(location_name: str) -> dict:
    """
    Retrieves geographical coordinates (latitude, longitude) for a given location name
    using OpenWeatherMap's Geocoding API ONLY. The LLM's grounding tool is expected
    to provide coordinates if this function fails.
    """
    global TOOL_CALL_LOG
    TOOL_CALL_LOG.append(f"get_coordinates_from_name({location_name})")
    print(f"Attempting OpenWeatherMap Geocoding for: '{location_name}'")
    if not OPENWEATHER_API_KEY:
        return {"status": "error", "error_message": "OpenWeatherMap API key not found."}

    # Try OpenWeatherMap Geocoding
    geocoding_url = (
        f"http://api.openweathermap.org/geo/1.0/direct?"
        f"q={location_name}&limit=1&appid={OPENWEATHER_API_KEY}"
    )

    try:
        response = requests.get(geocoding_url)
        response.raise_for_status()
        geo_data = response.json()

        if geo_data and len(geo_data) > 0:
            latitude = geo_data[0].get("lat")
            longitude = geo_data[0].get("lon")
            if latitude is not None and longitude is not None:
                print(f"Coordinates found via OpenWeatherMap Geocoding for '{location_name}': {latitude}, {longitude}")
                return {"status": "success", "data": {"latitude": latitude, "longitude": longitude}}
            
    except requests.exceptions.RequestException as e:
        print(f"OpenWeatherMap Geocoding failed for '{location_name}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred during OpenWeatherMap geocoding: {e}")

    # If OpenWeatherMap failed, do not attempt Google Search here.
    # The LLM's grounding will handle search if needed.
    return {"status": "error", "error_message": f"Could not find coordinates for '{location_name}' via OpenWeatherMap Geocoding."}


def get_weather_at_location(latitude: Optional[float], longitude: Optional[float], location_name: Optional[str] = None) -> dict:
    """
    Retrieves current weather information for a specified geographical location
    using OpenWeatherMap. It can now attempt to get coordinates from a name if lat/lon are not provided.
    """
    global TOOL_CALL_LOG
    TOOL_CALL_LOG.append(f"get_weather_at_location(lat={latitude}, lon={longitude}, loc='{location_name}')")
    if not OPENWEATHER_API_KEY:
        return {"status": "error", "error_message": "OpenWeatherMap API key not found. Please set OPENWEATHER_API_KEY in your .env file."}

    # If latitude or longitude are missing, try to get them from the location name
    # The LLM's grounding ability is expected to provide these if get_coordinates_from_name fails initially.
    if (latitude is None or longitude is None) and location_name:
        print(f"Latitude or Longitude missing. Attempting to get coordinates for '{location_name}' using get_coordinates_from_name...")
        coords_result = get_coordinates_from_name(location_name)
        if coords_result["status"] == "success":
            latitude = coords_result["data"].get("latitude")
            longitude = coords_result["data"].get("longitude")
        else:
            print(f"Could not get coordinates from name: {coords_result['error_message']}")
            return {"status": "error", "error_message": f"Unable to get coordinates for weather check. Reason: {coords_result['error_message']}"}

    if latitude is None or longitude is None:
        return {"status": "error", "error_message": "Latitude and Longitude are required for weather lookup and could not be determined."}


    print(f"Calling OpenWeatherMap API for weather at Lat: {latitude}, Lon: {longitude}")
    weather_url = (
        f"https://api.openweathermap.org/data/2.5/weather?"
        f"lat={latitude}&lon={longitude}&appid={OPENWEATHER_API_KEY}&units=metric"
    )

    try:
        response = requests.get(weather_url)
        response.raise_for_status()
        weather_data = response.json()

        # Extract main weather details
        temperature = weather_data["main"]["temp"]
        feels_like = weather_data["main"]["feels_like"]
        description = weather_data["weather"][0]["description"]
        wind_speed = weather_data["wind"]["speed"]
        city_name = weather_data.get("name", location_name) # Use OpenWeatherMap's city name, fallback to provided name

        report = (
            f"Current weather in {city_name} (Lat: {latitude}, Lon: {longitude}): "
            f"Temperature: {temperature}°C (feels like {feels_like}°C), "
            f"Description: {description}, Wind Speed: {wind_speed} m/s."
        )

        return {
            "status": "success",
            "data": {
                "temperature": temperature,
                "description": description,
                "wind_speed": wind_speed,
                "city": city_name,
                "report_text": report
            }
        }

    except requests.exceptions.RequestException as e:
        return {"status": "error", "error_message": f"Failed to fetch weather data: {e}"}
    except KeyError as e:
        return {"status": "error", "error_message": f"Missing expected data in weather response: {e}. Full response: {weather_data}"}
    except Exception as e:
        return {"status": "error", "error_message": f"An unexpected error occurred fetching weather: {e}"}


def summarize_delay_potential(launch_info: dict, weather_info: dict) -> dict:
    """
    Summarizes if a SpaceX launch might be delayed based on current weather conditions.
    This function helps the LLM combine the results from previous tools and
    make a judgment. It explicitly uses current weather due to API limitations for forecasts.
    """
    global TOOL_CALL_LOG
    TOOL_CALL_LOG.append("summarize_delay_potential")
    print("Summarizing delay potential based on launch and weather info...")

    launch_name = launch_info.get("name", "the upcoming launch")
    raw_launch_date_utc = launch_info.get("date_utc")
    try:
        # Parse the raw date string from launch_info (which might be ISO or "Unknown Date")
        launch_datetime_obj = datetime.datetime.fromisoformat(raw_launch_date_utc.replace('Z', '+00:00'))
        launch_date = launch_datetime_obj.strftime("%d %B %Y") # Format to "18 June 2025"
    except (ValueError, AttributeError):
        launch_date = "an unknown date" # If parsing fails, use fallback string

    launch_location_name = launch_info.get("location_info", {}).get("display_name", "an unknown location") # Use display_name here
    data_freshness_status = launch_info.get("data_freshness_status", "unknown")

    weather_description = weather_info.get("description", "unknown weather conditions")
    wind_speed = weather_info.get("wind_speed")
    temperature = weather_info.get("temperature")
    weather_city = weather_info.get("city", "the launch area")

    summary_text = (
        f"Current weather in {weather_city} (near {launch_location_name}):\n"
        f"Temperature: {temperature}°C (feels like {temperature}°C), " # Fixed feels_like not being used
        f"Description: {weather_description}, Wind Speed: {wind_speed} m/s.\n\n"
    )

    # Add the specific message if it's a past fallback date
    if data_freshness_status == "past_fallback":
        summary_text += (
            f"I am sorry, but as per the information available with me, the next launch date is {launch_date}. "
            f"I understand that this is a date from the past. I apologize that my data source "
            f"(the RocketLaunch.Live free API, with fallback to {SPACEX_API_BASE_URL} for past launches) is not updated with a future launch at this moment.\n\n"
        )
    elif data_freshness_status == "unknown":
         summary_text += (
            "Please note: The freshness of the launch data retrieved from the RocketLaunch.Live free API "
            "could not be fully determined, but the system proceeded with the available information.\n\n"
        )
    elif data_freshness_status == "no_spacex_in_next_5_fallback": # Add condition for this specific status
        summary_text = ( # OVERWRITE, not append, as per instruction to prepend response
            "None out of the next 5 global rocket launches is from SpaceX.\n\n" + summary_text
        )


    # Simple logic for delay prediction based on current weather
    delay_prediction = "Based on *current* conditions, the launch appears unlikely to be delayed due to weather."
    if "rain" in weather_description.lower() or "storm" in weather_description.lower():
        delay_prediction = "Current weather conditions (rain/storm) suggest a potential for delay."
    elif wind_speed and wind_speed > 10: # Example threshold for strong winds
        delay_prediction = "High winds might pose a risk, suggesting a potential for delay."
    elif temperature and (temperature < -5 or temperature > 35): # Example thresholds for extreme temps
        delay_prediction = "Extreme temperatures might affect launch readiness, suggesting a potential for delay."

    summary_text += f"Summary of delay potential for {launch_name} scheduled for {launch_date}: {delay_prediction} Please note that this assessment is based on *current* weather conditions, as forecast data for future launch dates is not available through the free APIs used."

    return {"status": "success", "summary": summary_text}


# --- The Main Agent (The "Manager") ---
# This is the 'root_agent' that Google ADK looks for. It. orchestrates everything.
# It uses the tools  defined above to fulfill user requests.
root_agent = Agent(
    name="space_weather_agent",
    model="gemini-2.0-flash", # Using Gemini model
    description=(
        "An agent that can find information about the next SpaceX launch, "
        "check the current weather at the launch location, and then summarize "
        "if the launch might be delayed due to weather conditions."
    ),
    instruction=(
        "You are a helpful assistant specialized in SpaceX launches and weather. "
        "Your goal is to answer user questions about upcoming launches and "
        "their potential for weather-related delays. "
        "When asked, you must first use `get_spacex_launch` to retrieve launch details. "
        "Examine the `data_freshness_status` from `launch_info`. If `data_freshness_status` is 'no_spacex_in_next_5_fallback', "
        "you *must* prepend your response with 'None out of the next 5 global rocket launches is from SpaceX.' "
        "Then, extract the launchpad's latitude and longitude from `launch_info.location_info`. "
        "If `latitude` or `longitude` are `None`, you *must* use `get_coordinates_from_name` "
        "with `location_name=launch_info.location_info.display_name`. If `get_coordinates_from_name` "
        "also fails to provide coordinates, you should then use your **internal Google Search capability** "
        "to find the most accurate latitude and longitude for the `launch_info.location_info.display_name`. "
        "Once coordinates are available (either directly from launch info, from `get_coordinates_from_name`, "
        "or through your own use of Google Search), you must call `get_weather_at_location` with "
        "the precise latitude and longitude. "
        "If both coordinates and a usable `display_name` are unavailable, clearly state the inability to get weather. "
        "Based on the user's explicit request, you should do one of the following:\n"
        "1. **If asked about the *launch date* or *launch time*:** Provide the `name` from `launch_info` and format the `date_utc` from `launch_info` as 'Day Month Year at HH:MM UTC' (e.g., '18 June 2025 at 05:38 UTC').\n"
        "2. **If asked about the *launchpad* or *location*:** Only provide the `display_name` from `launch_info.location_info`.\n"
        "3. **If asked about the *weather forecast* or *weather around the launch region*:** Only provide the `report_text` from `weather_info`.\n"
        "4. **If asked about the *impact of weather on the launch schedule* or a *summary*:** Call `summarize_delay_potential` using both `launch_info` and `weather_info`, and present its full `summary`.\n"
        "Always provide a comprehensive answer based on the information gathered by your tools, but only respond with the specific information the user asked for. If you encounter errors fetching data, inform the user about the error and try to proceed with available information or suggest a retry."
    ),
    # Register specialized helper functions as tools for the agent
    tools=[get_spacex_launch, get_launchpad_details_from_spacex_api, get_coordinates_from_name, get_weather_at_location, summarize_delay_potential],
)
