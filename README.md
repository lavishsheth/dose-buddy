# 💊 Dose Buddy

A medicine reminder built for one real person. Give it a prescription photo or plain text,
a local open model reads it, you confirm the result, and it sets reminders.

Everything runs on your own machine through [Ollama](https://ollama.com). No cloud AI, no API key,
and no health data leaves the laptop.

## Run it

```bash
# 1. Install Ollama, then pull an open model that can read images
ollama pull gemma3:4b

# 2. Install and start the app
pip install -r requirements.txt
streamlit run app.py

# 3. In a second terminal, start the reminder script
python reminder.py
```

## How it works

1. Type the instructions or upload a photo.
2. The model returns JSON (medicine, dose, times, days).
3. You check and edit every row. Nothing is saved until you confirm.
4. Reminders: download an `.ics` file for phone alarms (works offline),
   and/or run `reminder.py` for desktop alerts.

Optional Telegram messages (needs internet):

```bash
export TELEGRAM_BOT_TOKEN=your_bot_token
export TELEGRAM_CHAT_ID=your_chat_id
python reminder.py
```

## Files

- `app.py`: Streamlit interface
- `core.py`: prompt, parsing, schedule logic, .ics export
- `reminder.py`: background alerts

## Safety

This only sends reminders. It is not medical advice. Small models can misread handwriting or
doses, which is why the confirm-and-edit step exists. Always compare with the original prescription.
