For your convenience and direct use, this file contains set-up, installation and execution related extracts from README.md
For full project documentation, kindly refer to README.md



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



------------------------------------------------EVALUATION-------------------------------

RUNNING EVALS
To run the evaluation tests:

Ensure your evals.py file is in the my_space_agent directory (root directory)

Navigate to the my_space_agent directory in your activated virtual environment.

Execute the tests using the command:

python -m unittest evals.py


STATUS: 
All tests in evals.py are currently PASSING SUCCESSFULLY! 
This confirms the agent's core functionalities, tool chaining, routing logic, and response generation meet the defined evaluation criteria.



----------------------------------NOTE ON LIMITATIONS OF FREE APIs used-----------------

1. Free versions of OpenWeather APIs have been used. 
As these versions do not provide weather forecast data for future dates, the impact of local weather on space flight has been evaluated using current weather conditions at the launch location. 

2. Free version of the rocketlauch.live API provides info only for the next 5 global rocket launches. 


Free versions have been used keeping in view the demonstrative nature of this assignment. 
If needed, the model can subsequently be upgraded by using paid APIs which have a wider access.