# To install required packages:
# pip install panel openai==1.3.6 panel==1.3.4
# pip install git+https://github.com/microsoft/autogen.git
# pip install python-dotenv

import autogen
import panel as pn
import openai
import os
import time
import asyncio
from autogen import config_list_from_json
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key and assistant ID from environment variables
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
assistant_id = os.environ.get("ASSISTANT_ID", None)

# Initialize OpenAI client
client = OpenAI()


# Define configuration for GPT-4 model
config_list = [
    {
        'model': 'gpt-4-1106-preview',  # Specify the model to use, in this case, GPT-4
    }
]

# Define configuration for the assistant agent
llm_config = {
    "config_list": config_list,  # Pass the model configuration
    "seed": 36,  # Seed for reproducibility
    "assistant_id": assistant_id,  # ID of the assistant
    "tools": [
            {
                "type": "retrieval"  # Specify the type of tool the assistant can use
            }
        ],
    "file_ids": [],  # List of file IDs the assistant can access
}

# Initialize a Future object for asynchronous input handling
input_future = None

# Define a custom ConversableAgent class
class MyConversableAgent(autogen.ConversableAgent):

    # Asynchronous method to get human input
    async def a_get_human_input(self, prompt: str) -> str:
        global input_future
        chat_interface.send(prompt, user="System", respond=False)  # Send the prompt to the user
        # Create a new Future object for this input operation if none exists
        if input_future is None or input_future.done():
            input_future = asyncio.Future()

        # Wait for the callback to set a result on the future
        await input_future

        # Once the result is set, extract the value and reset the future for the next input operation
        input_value = input_future.result()
        input_future = None
        return input_value

# Initialize user proxy agent
user_proxy = MyConversableAgent(name="user_proxy",
    code_execution_config=False,  # Disable code execution for the user proxy
    is_termination_msg=lambda msg: "TERMINATE" in msg["content"],  # Define termination condition
    human_input_mode="ALWAYS")  # Set the human input mode to always

# Initialize GPT assistant agent
gpt_assistant = GPTAssistantAgent(name="assistant",
    instructions="You are adept at question answering",
    llm_config=llm_config)

# Define avatars for user and assistant
avatar = {user_proxy.name:"👨‍💼", gpt_assistant.name:"🤖"}

# Function to print messages
def print_messages(recipient, messages, sender, config):
    print(f"Messages from: {sender.name} sent to: {recipient.name} | num messages: {len(messages)} | message: {messages[-1]}")
    chat_interface.send(messages[-1]['content'], user=sender.name, avatar=avatar[sender.name], respond=False)
    return False, None  # required to ensure the agent communication flow continues

# Register reply functions for user and assistant
user_proxy.register_reply(
    [autogen.Agent, None],
    reply_func=print_messages, 
    config={"callback": None},
)
gpt_assistant.register_reply(
    [autogen.Agent, None],
    reply_func=print_messages, 
    config={"callback": None},
) 

# Initialize a flag for chat initiation
initiate_chat_task_created = False

# Asynchronous function to initiate chat after a delay
async def delayed_initiate_chat(agent, recipient, message):
    global initiate_chat_task_created
    # Indicate that the task has been created
    initiate_chat_task_created = True

    await asyncio.sleep(2)

    # Now initiate the chat
    await agent.a_initiate_chat(recipient, message=message)

    recipient.delete_assistant()

    if llm_config['file_ids'][0]:
        client.files.delete(llm_config['file_ids'][0])
        print(f"Deleted file with ID: {llm_config['file_ids'][0]}")

    time.sleep(5)

# Callback function for chat interface
async def callback(contents: str, user: str, instance: pn.chat.ChatInterface):
    global initiate_chat_task_created
    global input_future
    global gpt_assistant

    if not initiate_chat_task_created:
        asyncio.create_task(delayed_initiate_chat(user_proxy, gpt_assistant, contents))
    else:
        if input_future and not input_future.done():
            input_future.set_result(contents)
        else:
            print("There is currently no input being awaited.")

# Initialize Panel extension
pn.extension(design="material")

# Initialize a chat interface with a callback function, no button name, and specific sizing
chat_interface = pn.chat.ChatInterface(
    callback=callback,
    show_button_name=False,
    sizing_mode="stretch_both",
    min_height=600,
)

# Send an initial message from the system to the user
chat_interface.send("Ask your question about the document!!", user="System", respond=False)

# Initialize a loading spinner for file uploads
uploading = pn.indicators.LoadingSpinner(value=False, size=50, name='No document')

# Initialize a file input widget for PDF files
file_input = pn.widgets.FileInput(name="PDF File", accept=".pdf")

# Initialize a text area input widget for file information
text_area = pn.widgets.TextAreaInput(name='File Info', sizing_mode='stretch_both', min_height=600)

# Define a callback function for file input value changes
def file_callback(*events):
    # Loop through all events
    for event in events:
        # If the event is a filename change, store the new filename
        if event.name == 'filename':
            file_name = event.new
        # If the event is a value change, store the new value (file content)
        if event.name == 'value':
            file_content = event.new
    
    # Indicate that a file is being uploaded
    uploading.value = True
    uploading.name = 'Uploading'
    file_path = file_name

    # Write the file content to a file
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    # Try to upload the file to the OpenAI API
    try:
        response = client.files.create(file=open(file_path, 'rb'), purpose='assistants')
        print(f"File upload response: {response}")
    except Exception as e:
        print(f"Error during file upload: {e}")
    
    # Wait until the file is found in the list of all files
    found = False
    while not found:
        all_files = client.files.list()  # Retrieve the list of all files
        for file in all_files.data:
            if file.id == response.id:
                found = True
                print(f"Uploaded file with ID: {response.id}\n {file}")
                
                # Update the assistant agent with the new file ID
                global gpt_assistant
                llm_config['file_ids'] = [file.id]
                gpt_assistant.delete_assistant()
                gpt_assistant = GPTAssistantAgent(name="assistant",
                                instructions="You are adept at question answering",
                                llm_config=llm_config)
                gpt_assistant.register_reply(
                                    [autogen.Agent, None],
                                    reply_func=print_messages, 
                                    config={"callback": None},
                                ) 

                # Update the text area with the file information
                text_area.value = str(client.files.retrieve(file.id))

                # Indicate that the file upload is complete
                uploading.value = False
                uploading.name = f"Document uploaded - {file_name}"
                break 
        if not found:
            time.sleep(5)

# Set up a callback on file input value changes
file_input.param.watch(file_callback, ['value', 'filename'])

# Define the title and layout of the application
title = '## Please upload your document for RAG'
file_app = pn.Column(pn.pane.Markdown(title), file_input, uploading, text_area, sizing_mode='stretch_width', min_height=500)

# Define the template of the application and make it servable
pn.template.FastListTemplate(
    title="📚AutoGen w/ RAG",
    header_background="#2F4F4F",
    accent_base_color="#2F4F4F",
    main=[
        chat_interface
    ],
    sidebar=[file_app],
    sidebar_width=400,
).servable()