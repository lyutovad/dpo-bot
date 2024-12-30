from web_app import WebApp
import asyncio

if __name__ == "__main__":
    app = WebApp()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.init_web_app())
    
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Server stopped.")
    