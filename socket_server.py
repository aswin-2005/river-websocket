import asyncio
import websockets
import requests
import os
import json
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




clients = {}






async def cleanup_task():
    while True:
        try:
            # Get list of active users from clients dictionary
            active_users = list(clients.keys())
            
            # Call cleanup API
            response = requests.post(
                os.getenv('FLASK_SERVER_URL') + '/cleanup',
                json={'active_users': active_users}
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Cleanup completed: {result['removed_count']} users removed")
            else:
                logger.error(f"Cleanup failed with status code: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
        # Wait for 10 seconds before next cleanup
        await asyncio.sleep(10)






async def echo(websocket):





    try:
        username = await websocket.recv()
        token = await websocket.recv()
        response = requests.post(os.getenv('FLASK_SERVER_URL') + '/validate-token', json={'username': username, 'token': token})
        if response.status_code == 200:
            clients[username] = websocket
            # Broadcast to all clients that a new user joined
            join_message = f"{username} has joined the chat"
            logger.info(join_message)
            for client in clients.values():
                await client.send(json.dumps({"code": 100, "sender": 'SYSTEM', "message": join_message, "active_users" : list(clients.keys())}))
        else:
            await websocket.send(json.dumps({"code": 300, "sender": 'SYSTEM', "message": "Corrupted Connection, Closing..."}, ensure_ascii=False))
            await websocket.close()







        try:
            async for message in websocket:
                # Broadcast message to all clients
                broadcast_message = f"{username}: {message}"
                logger.info(broadcast_message)
                for client in clients.values():
                    await client.send(json.dumps({"code": 200, "sender": username, "message": message}))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {username} connection closed")
            requests.post(os.getenv('FLASK_SERVER_URL') + '/logout', json={'username': username})
        except Exception as e:
            logger.error(f"Error handling message from {username}: {e}")





    finally:
        if username in clients:
            del clients[username]
            # Broadcast that user has left
            leave_message = f"SYSTEM: {username} has left the chat"
            logger.info(leave_message)
            for client in clients.values():
                await client.send(json.dumps({"code": 100, "sender": 'SYSTEM', "message": leave_message, "active_users" : list(clients.keys())}))





async def main():
    try:
        # Start the cleanup task
        cleanup_loop = asyncio.create_task(cleanup_task())
        
        async with websockets.serve(echo, '0.0.0.0', 8765) as server:
            logger.info("WebSocket server started on ws://0.0.0.0:8765")
            await server.serve_forever()
    except Exception as e:
        logger.error(f"Server error: {e}")






if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal server error: {e}")
