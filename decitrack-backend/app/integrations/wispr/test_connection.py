
import asyncio
import traceback

from app.integrations.wispr.client import discover_wispr_tools


async def main():
    print("=" * 55)
    print("DECITRACK - WISPR FLOW CONNECTION TEST")
    print("=" * 55)

    try:
        tools = await discover_wispr_tools()

        print(f"\nConnection successful!")
        print(f"Discovered {len(tools)} tools:\n")

        for index, tool in enumerate(tools, start=1):
            print(f"{index}. {tool['name']}")
            print(f"Description: {tool['description']}")
            print(f"Input schema: {tool['input_schema']}")
            print("-" * 55)

    except BaseException as exc:
        print("\nFULL ERROR DETAILS:")
        traceback.print_exception(type(exc), exc, exc.__traceback__)

        if isinstance(exc, BaseExceptionGroup):
            print("\nNESTED EXCEPTIONS:")
            for index, nested in enumerate(exc.exceptions, start=1):
                print(f"\nException {index}:")
                traceback.print_exception(
                    type(nested), nested, nested.__traceback__
                )


if __name__ == "__main__":
    asyncio.run(main())
