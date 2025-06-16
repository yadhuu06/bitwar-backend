async def send_error(consumer, message, code=4000):
    """Send an error message to the WebSocket client."""
    try:
        await consumer.send_json({
            'type': 'error',
            'message': message
        })
        if code != 4000:
            await consumer.close(code=code)
    except Exception as e:
        print(f"[ERROR] Failed to send error message: {str(e)}")
        await consumer.close(code=4000)