import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
import streamlit as st
import itertools
import time
from langchain_core.messages import HumanMessage

load_dotenv()
print(f"DEBUG: GEMINI_API_KEY after load_dotenv(): {os.getenv('GEMINI_API_KEY')[:5] + '...' if os.getenv('GEMINI_API_KEY') else 'None'}") # Debug print

class LLMManager:
    def __init__(self):
        self.openai_api_keys = self._get_api_keys("OPENAI_API_KEY")
        self.google_api_keys = self._get_api_keys("GEMINI_API_KEY")
        self.groq_api_keys = self._get_api_keys("GROQ_API_KEY")

        self.openai_key_iterator = itertools.cycle(self.openai_api_keys) if self.openai_api_keys else None
        self.google_key_iterator = itertools.cycle(self.google_api_keys) if self.google_api_keys else None
        self.groq_key_iterator = itertools.cycle(self.groq_api_keys) if self.groq_api_keys else None

    def _get_api_keys(self, env_var_prefix):
        keys = []
        # 먼저 접미사 없는 기본 환경 변수 이름으로 시도
        key = os.getenv(env_var_prefix)
        if key:
            keys.append(key)
        
        # 이어서 _1부터 _10까지 접미사가 붙은 환경 변수 이름으로 시도
        for i in range(1, 11):
            env_var_name = f"{env_var_prefix}_{i}"
            key = os.getenv(env_var_name)
            if key:
                keys.append(key)
        return keys

    def get_llm(self, provider: str, model_name: str):
        llm = None
        api_key = None
        try:
            if provider == "OpenAI":
                if not self.openai_api_keys:
                    print("OpenAI API 키가 설정되지 않았습니다.")
                    return None
                api_key = next(self.openai_key_iterator)
                llm = ChatOpenAI(model_name=model_name, api_key=api_key, temperature=0)
            elif provider == "Google":
                if not self.google_api_keys:
                    print("Google API 키가 설정되지 않았습니다.")
                    return None
                api_key = next(self.google_key_iterator)
                llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=0)
            elif provider == "GROQ":
                if not self.groq_api_keys:
                    print("GROQ API 키가 설정되지 않았습니다.")
                    return None
                api_key = next(self.groq_key_iterator)
                llm = ChatGroq(model_name=model_name, groq_api_key=api_key, temperature=0)
            else:
                print(f"지원하지 않는 LLM 제공사: {provider}")
                return None
            return llm
        except Exception as e:
            print(f"{provider} LLM 초기화 중 오류 발생 (API 키: {api_key[:5]}...): {e}")
            return None

    def call_llm_with_retry(self, llm, prompt, max_retries=5, delay=1):
        for i in range(max_retries):
            try:
                # 'prompt'는 문자열(텍스트 모델용)이거나 딕셔너리 목록(멀티모달용)일 수 있습니다.
                # llm.invoke는 메시지 목록을 예상합니다.
                # 따라서 문자열이면 래핑하고, 딕셔너리 목록이면 HumanMessage로 래핑합니다.
                if isinstance(prompt, list) and all(isinstance(p, dict) for p in prompt): # 멀티모달 콘텐츠 목록
                    messages = [HumanMessage(content=prompt)]
                elif isinstance(prompt, str): # 텍스트 콘텐츠 문자열
                    messages = [HumanMessage(content=prompt)]
                else: # 이미 메시지 목록이라고 가정 (예: 채팅 기록에서)
                    messages = prompt

                response = llm.invoke(input=messages)
                return response.content
            except Exception as e:
                print(f"LLM 호출 실패 (재시도 {i+1}/{max_retries}): {e}")
                time.sleep(delay * (2 ** i)) # Exponential backoff
        print(f"LLM 호출 {max_retries}회 실패. 작업을 중단합니다.")
        return None
