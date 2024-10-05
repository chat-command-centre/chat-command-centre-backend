#!/usr/bin/env python3
"""Module for openai.py"""


import openai


class OpenAIIntegration:
    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = self.api_key

    def generate_text(self, prompt: str, **kwargs) -> str:
        response = openai.Completion.create(
            engine="text-davinci-003", prompt=prompt, **kwargs
        )
        return response.choices[0].text.strip()


if __name__ == "__main__":
    main()
