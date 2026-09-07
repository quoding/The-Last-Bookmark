from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/tainai"

    llm_api_key: str = ""
    llm_model: str = "gpt-5.6-luna"

    image_api_key: str = ""
    image_model: str = "gpt-image-2"
    image_quality: str = "low"
    image_size: str = "1024x1536"

    invite_code_hashes: str = ""  # "code_id:sha256hash,code_id:sha256hash"
    auth_secret: str = "dev-secret-change-me"

    # 코드별로 다른 API 키를 쓰기 위한 매핑. "code_id:api_key,code_id:api_key" 형식.
    # muya98(개발/테스트용)과 tainai(제공용) 같은 코드마다 비용을 분리 추적하려는 용도다.
    # LLM·이미지 호출 모두 이 하나의 키를 공유해서 쓴다. 매핑에 없는 code_id는
    # 전역 LLM_API_KEY/IMAGE_API_KEY로 폴백한다.
    code_api_keys: str = ""

    image_budget_sessions: int = 3  # 코드 1개당 저장 가능한 회차 수 상한
    storage_path: str = "./storage"

    # 관리자 전용 비용 모니터링 페이지(/admin, /api/admin/usage) 접근 비밀번호.
    # 비워두면 관리자 라우트 전체가 비활성화된다.
    admin_password: str = ""

    # 콤마 구분 origin 목록. 프론트(Codex)는 별도 origin(Vite dev 서버, quoding.com)에서
    # 호출하므로 CORS 허용 목록이 필요하다. 기본값은 로컬 개발 편의를 위한 것이다.
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    def _code_api_key_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for pair in self.code_api_keys.split(","):
            pair = pair.strip()
            if not pair:
                continue
            code_id, _, api_key = pair.partition(":")
            if code_id and api_key:
                result[code_id] = api_key
        return result

    def resolve_api_key(self, code_id: str, default: str) -> str:
        return self._code_api_key_map().get(code_id, default)


@lru_cache
def get_settings() -> Settings:
    return Settings()
