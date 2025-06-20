SPACEX-WEATHER AGENT
This project features a multi-agent system designed to provide information about SpaceX launches and assess their potential for weather-related delays. The agent leverages external APIs to gather real-time data and employs an advanced Large Language Model for intelligent decision-making and response generation.


AGENT OVERIEW:
Our core agent is powered by Gemini using the gemini-2.0-flash model. It acts as a helpful assistant specializing in SpaceX launch data and weather analysis. The agent's primary functions include:

--Retrieving SpaceX Launch Details: Fetches information about upcoming (or the latest past successful) SpaceX missions.

--Checking Current Weather Conditions: Obtains real-time weather data for the launch location.

--Summarizing Delay Potential: Analyzes launch and weather data to provide a concise summary on potential weather-related delays.



SPECIAL FEATURES OF THE AGENT: 
This agent incorporates several key design principles and capabilities:

--ROBUST DATE AND TIME EXTRACTION & FORMATTING 
The get_spacex_launch tool includes SOPHISTICATED DATE PARSING LOGIC to extract launch times from various fields (win_open, t0, sort_date, est_date, launch_description, quicktext, date_str). The agent's instruction then ensures the date and time are always displayed to the user in a USER-FRIENDLY 'DAY MONTH YEAR AT HH:MM UTC' FORMAT (e.g., '20 June 2025 at 10:00 UTC') for all relevant queries.

--INTELLIGENT FALLBACK MECHANISM FOR LAUNCH DATA
The agent prioritizes the MOST RELEVANT UPCOMING SPACEX LAUNCH from RocketLaunch.Live's "next 5" API. 
If no SpaceX launches are found in this immediate list, it gracefully falls back to retrieving the LATEST SUCCESSFUL PAST SPACEX LAUNCH from the historical SpaceX API, clearly communicating this to the user.


--SEAMLESS COORDINATE RETRIEVAL WITH LLM GROUNDING 
The agent first attempts to get launchpad coordinates from the get_spacex_launch tool or get_coordinates_from_name. 
If these explicit tools fail, it leverages the Gemini model's INTERNAL GOOGLE SEARCH CAPABILITY to implicitly find the necessary coordinates, ensuring high robustness in location data acquisition.


--CONTEXT-AWARE RESPONSE GENERATION
The root_agent's detailed instruction allows the LLM to intelligently tailor its final response, providing only the SPECIFIC INFORMATION REQUESTED BY THE USER (e.g., just the date, just the location, or a full weather impact summary).


--EXPLICIT JSON SCHEMA INSTRUCTION 
The agent's instructions provide guidance on the EXPECTED STRUCTURE OF DATA returned by the get_spacex_launch tool, enabling the underlying LLM to robustly parse and understand the information for subsequent steps.





---------------------------------------SETUP AND INSTALLATION---------------------------------

To run this project, you'll need Python 3.9+ and the necessary dependencies.


-- PROJECT's DIRECTORY AND FILE STRUCTURE

my_space_agent/
├── multi_tool_agent/
│   ├── __init__.py
│   └── agent.py
├── .env
├── evals.py
└── requirements.txt


CREATE AND ACTIVATE A VIRTUAL ENVIRONMENT WITHIN DIRECTORY NAMED my_space_agent
To create and activate a virtual environment, use these commands from your my_space_agent directory (the root directory)

To create virtual environment named venv: 
python -m venv venv

To activate the virtual environment:
.\venv\Scripts\activate  # On Windows
source venv/bin/activate # On macOS/Linux


INSTALL DEPENDENCIES:
From the my_space_agent directory, run the following command to install dependencies:

pip install -r requirements.txt
# Ensure your requirements.txt includes: google-generativeai, python-dotenv, requests, google-adk, pytz


CONFIGURE THE API KEYS:
Get your OpenWeatherMap API key from OpenWeatherMap.
Get your Google Generative AI API key from Google AI Studio.

In the .env file, insert your API keys at the location provided.
Contents of .env file are produced below for refernce.  
Avoid using space around '=' while inserting the API keys. 

OPENWEATHER_API_KEY=YOUR_OPENWEATHER_API_KEY
GOOGLE_API_KEY=YOUR_GOOGLE_GENERATIVE_AI_API_KEY




RUNNING THE AGENT:
You can interact with the agent through the Google ADK runtime:

To run locally (command-line chat interface), use the following command:
adk run multi_tool_agent

To run as a web service (browser-based chat interface), use the following command:
adk web



EVALUATION:
The project includes a COMPREHENSIVE AUTOMATED EVALUATION SUITE via the evals.py script for rigorous testing of the agent's performance.


Purpose of evals.py
The evals.py script is designed to programmatically check your agent's behavior and verify key aspects of its functionality:


--TEST GOAL SATISFACTION: Verifies that the agent produces the correct final response for various user queries, including accurate date and time formatting.

--EVALUATE AGENT TRAJECTORY (TOOL CHAINING & ROUTING LOGIC): Examines the precise sequence of internal tool calls and their arguments. This ensures the agent's "planner" is functioning as expected, orchestrating tools efficiently.

--ASSESS ITERATIVE REFINEMENT: Tests scenarios where the agent handles missing information or tool failures, such as simulating get_coordinates_from_name failure to confirm successful fallback to implicit Google Search grounding.


HOW IT WORKS (with Logging Integration)
The evals.py script utilizes Python's unittest framework and unittest.mock.patch to:

MOCK EXTERNAL APIS: Replaces actual calls to external services (like OpenWeatherMap and the core Gemini API) with pre-defined, controlled responses, ensuring repeatable and isolated tests.

SIMULATE AGENT LOGIC: Simulates the agent's internal decision-making process for calling tools.

TOOL CALL LOGGING FOR DEBUGGING AND ANALYSIS: A TOOL_CALL_LOG global variable in agent.py (accessed by evals.py) records every tool function call during execution. This allows evals.py to inspect the agent's step-by-step execution and verify that the expected tools were called in the correct order for different scenarios.

ASSERT OUTCOMES: Tests then assert against the agent's final text response (for goal satisfaction) and inspect the TOOL_CALL_LOG (for trajectory and routing logic).



RUNNING EVALS
To run the evaluation tests:

Ensure your evals.py file is in the my_space_agent directory (root directory)

Navigate to the my_space_agent directory in your activated virtual environment.

Execute the tests using the command:

python -m unittest evals.py


STATUS: 
All tests in evals.py are currently PASSING SUCCESSFULLY! 
This confirms the agent's core functionalities, tool chaining, routing logic, and response generation meet the defined evaluation criteria.


Code Quality and Documentation
The project prioritizes clean, readable, and well-commented code. The comprehensive evals.py script and this detailed README.md reflect a strong commitment to robust testing and clear documentation, outlining the agent's design, functionality, and how its performance is measured.


-------------------------------------------------- END OF SET UP AND EVALUATION --------------------------------


NOTE ON LIMITATIONS OF FREE APIs used: 

1. Free versions of OpenWeather APIs have been used. 
As these versions do not provide weather forecast data for future dates, the impact of local weather on space flight has been evaluated using current weather conditions at the launch location. 

2. Free version of the rocketlauch.live API provides info only for the next 5 global rocket launches. 


Free versions have been used keeping in view the demonstrative nature of this assignment. 
If needed, the model can subsequently be upgraded by using paid APIs which have a wider access.




