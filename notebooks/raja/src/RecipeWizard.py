
from typing import List
from pydantic import BaseModel
from pydantic import Field

from langchain.chains import LLMChain
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_openai import ChatOpenAI
from openai import OpenAI
import gradio as gr

from src.helper import parse_json_markdown
from src.helper import convert_to_md
from src.helper import get_chat_llm
from src.helper import get_image_llm

import os


SYSTEM_PROMPT='You are an extemely talented and top Chef with expertise in every type of cuisine and can make delicious food.Generate receipe a dinner receipe with name, ingredients and step by step instructions.'

class Recipe(BaseModel):
    dishName: str = Field(description="Recipe Name")
    ingredients: List[str] = Field(description="All ingredients for the recipe")
    cookingInstructions: str = Field(description="Step by Step instructions on how to cook the dish")

def getChatLLM(model_name, api_key):

    if model_name.startswith("gpt-"):
        return ChatOpenAI(model_name=model_name, openai_api_key=api_key, streaming=True)
    elif model_name.startswith("gemini-"):
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, streaming=True)
    else:
        raise ValueError(f"Unsupported model: {model_name}")
    return 

def getRecipeImage(model_name, api_key, recipeDetails):

    image_params = {
        "model": "dall-e-3",  
        "n": 1,               
        "size": "1024x1024",  
        "prompt": f'Authentic dish image of {recipeDetails}' 
        }
   
    try:
        image_llm = get_image_llm(model_name, api_key)
        response_image = image_llm.images.generate(**image_params)
        return response_image.data[0].url
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return ""

def getRecipe(user_prompt, history, model_name, api_key, image_model_name, image_api_key):

    recipe_out_parser = PydanticOutputParser(pydantic_object=Recipe)
    history_langchain_format = []
    history_langchain_format.append(('system', SYSTEM_PROMPT))


    for msg in history:
        if msg['role'] == "user":
            history_langchain_format.append(('human', msg['content']))
        elif msg['role'] == "assistant":
            history_langchain_format.append(('ai', msg['content']))

    history_langchain_format.append(('human', user_prompt))
    history_langchain_format.append(("human", "Here is your recipe \n{format_instructions}\n{query}"))

    recipe_prompt = ChatPromptTemplate.from_messages(history_langchain_format)
    recipe_prompt.input_variables=["query"]
    recipe_prompt.output_parser = recipe_out_parser
    recipe_prompt.partial_variables = {"format_instructions": recipe_out_parser.get_format_instructions()}

    model = get_chat_llm(model_name, api_key)
    llm_chain = LLMChain(llm=model, prompt=recipe_prompt)
    outputRecipe = llm_chain.run("Give me receipe")

    recipe_json = parse_json_markdown(outputRecipe)

    print(f"THIS IS THE DISH : {recipe_json['dishName']}") 
    print(f"ITS INGREDIENTS : {''.join(recipe_json['ingredients'])}")

    if image_model_name == "No Image":
        recipeImageURL = ''
    else:
        recipeImageURL = getRecipeImage(image_model_name, image_api_key, recipe_json['dishName']) 
        

    print (f"Image URL: {recipeImageURL}")

    return convert_to_md(outputRecipe, recipeImageURL)

def predict(message, history, model_name, api_key, image_model_name, image_api_key):
    history_langchain_format = []
    history_langchain_format.append(SystemMessage(SYSTEM_PROMPT))
    for msg in history:
        if msg['role'] == "user":
            history_langchain_format.append(HumanMessage(content=msg['content']))
        elif msg['role'] == "assistant":
            history_langchain_format.append(AIMessage(content=msg['content']))
    history_langchain_format.append(HumanMessage(content=message))
    llm_response = getRecipe(message, history, model_name, api_key, image_model_name, image_api_key)
    return llm_response


def reset():
    return [], []
def resetAllData():
    return [], [], '', ''
def reset_all(key):
    return [], [], ''



# def startWizard(chat_model, image_model):
def startWizard():

    with gr.Blocks() as demo:

        title = gr.Markdown(
            """
            # Recipe Wizard !
            This is a slick bot that can give you amazing recipes. You can ask to give recipe based on ingredients, choices and ask to modify given recipe.

            <span style="color:blue;"> | Note: Currenly only OpenAI and Gemini chat and Gemini image model supported. </span>
            """)
            
        with gr.Row():
            llmmodel = gr.Dropdown(
                label="LLM Model",
                choices=["gpt-4o-mini", "gemini-1.5-pro"],
                allow_custom_value=True
            )
            llm_apikey = gr.Textbox(label="API Key")
        with gr.Row():

            image_llmmodel = gr.Dropdown(
                label="Image Model",
                choices=["No Image", "dall-e-3"],
                allow_custom_value=True
            )
            image_llm_apikey = gr.Textbox(label="Image API Key", render=True, interactive=True)

        bot = gr.Chatbot(type="messages", render=False)
        # slider = gr.Slider(10, 100, render=False)
        chat = gr.ChatInterface(
            chatbot=bot,
            fn=predict, 
            additional_inputs=[llmmodel, llm_apikey, image_llmmodel, image_llm_apikey], type="messages"
        )
        with gr.Row():
            clear = gr.Button("Clear")
            clear_all = gr.Button("Clear All")

        # clear.click(lambda: None, None, chatbot, queue=False)
        clear.click(fn=reset, outputs=[bot, chat.chatbot_state])
        clear_all.click(fn=resetAllData, outputs=[bot, chat.chatbot_state,llm_apikey, image_llm_apikey])
        llmmodel.input(fn=reset_all, inputs=llmmodel, outputs=[bot, chat.chatbot_state, llm_apikey])
        image_llmmodel.input(fn=reset_all, inputs=image_llmmodel, outputs=[bot, chat.chatbot_state, image_llm_apikey])
        
    demo.launch()
