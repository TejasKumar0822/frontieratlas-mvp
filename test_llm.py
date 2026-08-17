import asyncio

from dotenv import load_dotenv

from src.llm.orchestrator import LLMOrchestrator


load_dotenv()


async def main():
    llm = LLMOrchestrator()

    schema = {
        "recordType": "STARTUP",
        "content": {
            "entityName": "string or null",
            "employeeCount": "integer or null"
        }
    }

    source_text = """
    Company: OpenAI.
    Employees: 1000.
    """

    result = await llm.extract(source_text, schema)

    print("\nLLM RESULT:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())