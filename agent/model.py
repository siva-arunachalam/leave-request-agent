import os
import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.azure import AzureProvider
from azure.identity import get_bearer_token_provider, ClientSecretCredential
from openai import AsyncAzureOpenAI

def azure_openai_model_old(endpoint=None, deployment=None):
    credential = ClientSecretCredential(
        tenant_id=os.getenv("SP_TENANT_ID"),
        client_id=os.getenv("SP_CLIENT_ID"),
        client_secret=os.getenv("SP_CLIENT_SECRET"),
    )
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token
    endpoint = endpoint or os.getenv('AZURE_OPENAI_ENDPOINT')
    deployment = deployment or os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')

    client = AsyncAzureOpenAI(
        api_key=token,
        azure_endpoint=endpoint,
        api_version="2024-10-21",
    )
    model = OpenAIModel(deployment, provider=AzureProvider(openai_client=client))
    return model


def azure_openai_model(endpoint=None, deployment=None):
    endpoint = endpoint or os.getenv('AZURE_OPENAI_ENDPOINT')
    deployment = deployment or os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')

    credential = ClientSecretCredential(
        tenant_id=os.getenv("SP_TENANT_ID"),
        client_id=os.getenv("SP_CLIENT_ID"),
        client_secret=os.getenv("SP_CLIENT_SECRET"),
    )

    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2025-03-01-preview",
    )

    model = OpenAIModel(deployment, provider=AzureProvider(openai_client=client))
    return model

async def test_model(prompt):
    model = azure_openai_model()
    agent = Agent(model)
    return await agent.run(prompt)

if __name__ == "__main__":
    response = asyncio.run(test_model("did I say no?"))
    print(response.data)
