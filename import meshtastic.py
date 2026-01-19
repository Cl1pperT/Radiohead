import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import time
import sys


TRIGGER_WORD = "jarvis"   # case-insensitive


def on_receive(packet, interface):
    """
    Called whenever a packet is received from Meshtastic.
    """

    try:
        decoded = packet.get("decoded", {})
        portnum = decoded.get("portnum")

        # Only care about text messages
        if portnum != "TEXT_MESSAGE_APP":
            return

        text = decoded.get("payload", "").decode("utf-8", errors="ignore").strip()

        if not text:
            return

        print(f"\n📡 Incoming: {text}")

        # Check trigger word
        if not text.lower().startswith(TRIGGER_WORD):
            print("⏭️  Ignored (no Jarvis trigger)")
            return

        # Remove trigger word
        user_message = text[len(TRIGGER_WORD):].strip(" ,:")

        print("✅ Triggered Jarvis")
        print(f"🧠 User message: {user_message}")

        # Build LLM prompt (we'll send this to Ollama later)
        llm_prompt = build_llm_prompt(user_message)

        print("\n--- LLM PROMPT ---")
        print(llm_prompt)
        print("------------------\n")

    except Exception as e:
        print("❌ Error processing packet:", e)


def build_llm_prompt(user_message: str) -> str:
    """
    Prompt designed for VERY short radio responses.
    """

    return f"""
You are Jarvis, a tiny assistant running on a low-bandwidth radio mesh.

Rules:
- Respond in ONE short sentence.
- Maximum 20 words.
- No emojis.
- No explanations.
- Be clear and direct.
- If unsure, say you do not know.

User message:
"{user_message}"

Reply:
""".strip()


def main():
    print("🔌 Connecting to Meshtastic node over USB...")

    try:
        interface = meshtastic.serial_interface.SerialInterface()
    except Exception as e:
        print("❌ Failed to connect:", e)
        sys.exit(1)

    pub.subscribe(on_receive, "meshtastic.receive")

    print("✅ Connected. Listening for messages...")
    print("Say:  Jarvis what time is it")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Exiting")
        interface.close()


if __name__ == "__main__":
    main()
