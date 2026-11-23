"""HTTP/WebSocket server: uvicorn farolito_env.app:app --port 8000"""

from openenv.core.env_server.http_server import create_app

from farolito_env.environment import FarolitoEnvironment
from farolito_env.models import FarolitoAction, FarolitoObservation

app = create_app(FarolitoEnvironment, FarolitoAction, FarolitoObservation, env_name="farolito", max_concurrent_envs=4)


def main() -> None:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    uvicorn.run(app, host=a.host, port=a.port)


if __name__ == "__main__":
    main()
