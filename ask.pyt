import sys

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()


def main():
    if len(sys.argv) < 2:
        print("Usage: python ask.py \"<question>\"")
        sys.exit(1)

    question = " ".join(sys.argv[1:])

    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": question}],
    )

    for block in response.content:
        if block.type == "text":
            print(block.text)


if __name__ == "__main__":
    main()
