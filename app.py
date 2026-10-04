"""Dose Buddy: turn a prescription photo or plain text into a reminder schedule.
Everything runs locally through Ollama, so health data never leaves the laptop."""
from datetime import date, datetime

import ollama
import pandas as pd
import streamlit as st

import core

st.set_page_config(page_title="Dose Buddy", page_icon="💊")
st.title("💊 Dose Buddy")
st.caption("A medicine reminder that reads the prescription for you. "
           "Runs on a local open model, so nothing is sent to the cloud.")

with st.sidebar:
    st.header("Settings")
    person = st.text_input("Who is this for?", value="Dad")
    model = st.text_input("Ollama model", value="gemma3:4b",
                          help="Use a vision-capable model (like gemma3) to read photos.")
    host = st.text_input("Ollama address", value="http://localhost:11434")
    start = st.date_input("First day of the course", value=date.today())
    try:
        ollama.Client(host=host).list()
        st.success("Ollama is running")
    except Exception:
        st.error("Can't reach Ollama. Start it with `ollama serve`.")

st.warning("This app only reminds. It is not medical advice. "
           "Always check the schedule against the prescription before saving.")

tab_add, tab_today, tab_remind = st.tabs(["1. Add medicines", "2. Today", "3. Get reminders"])


def read_with_ai(text, image_bytes):
    msg = {"role": "user", "content": "Extract the medicine schedule.\n\n" + (text or "")}
    if image_bytes:
        msg["images"] = [image_bytes]
    resp = ollama.Client(host=host).chat(
        model=model,
        messages=[{"role": "system", "content": core.SYSTEM_PROMPT}, msg],
        format="json",
        options={"temperature": 0},
    )
    return core.extract_meds(resp["message"]["content"])


def to_df(meds):
    return pd.DataFrame([{**m, "times": ", ".join(m["times"])} for m in meds],
                        columns=["name", "dose", "times", "days", "notes"])


with tab_add:
    text = st.text_area("Type the instructions", height=100,
                        placeholder="Paracetamol 500mg after dinner. "
                                    "Amoxicillin 250mg every 8 hours for 5 days.")
    photo = st.file_uploader("...or upload a photo of the prescription or strip",
                             type=["png", "jpg", "jpeg"])
    if st.button("Read with AI", type="primary", disabled=not (text or photo)):
        with st.spinner("Reading..."):
            try:
                meds = read_with_ai(text, photo.getvalue() if photo else None)
                st.session_state.draft = to_df(meds)
                if not meds:
                    st.error("The model found no medicines. Try rewording or a clearer photo.")
            except Exception as e:
                st.error(f"Model call failed: {e}")

    if "draft" in st.session_state:
        st.subheader("Check every row before saving")
        st.caption("Times are 24-hour (21:00 = 9 PM). Days = 0 means ongoing. "
                   "Fix anything the AI got wrong.")
        edited = st.data_editor(st.session_state.draft, num_rows="dynamic",
                                use_container_width=True)
        if st.button("Confirm and save"):
            meds = [core.normalize_med(r) for r in edited.to_dict("records")]
            bad = [m["name"] or "(no name)" for m in meds
                   if not m["name"] or not m["times"] or m["name"] == "UNCLEAR"
                   or m["dose"] == "UNCLEAR"]
            if bad:
                st.error("Please fix these rows (missing name, dose, or valid time): "
                         + ", ".join(bad))
            elif not meds:
                st.error("Nothing to save.")
            else:
                core.save_schedule(person, start, meds)
                st.success("Saved. See the Today and Get reminders tabs.")

saved = core.load_schedule()

with tab_today:
    if not saved:
        st.info("No schedule saved yet.")
    else:
        st.subheader(f"{saved['person']}'s doses today")
        doses = core.doses_for_day(saved["medicines"], saved["start"], date.today())
        if not doses:
            st.write("Nothing due today.")
        now = datetime.now().strftime("%H:%M")
        for t, name, dose, notes in doses:
            mark = "✅ done time" if t < now else "⏰ upcoming"
            st.write(f"**{t}**  {name} {dose}  {('(' + notes + ')') if notes else ''}  {mark}")

with tab_remind:
    if not saved:
        st.info("Save a schedule first.")
    else:
        st.subheader("Option A: phone alarms (works offline)")
        st.write("Download this calendar file and open it on the phone. "
                 "Each dose becomes a repeating alarm.")
        st.download_button("Download reminders (.ics)",
                           core.make_ics(saved["person"], saved["start"], saved["medicines"]),
                           file_name="medicine-reminders.ics", mime="text/calendar")
        st.subheader("Option B: reminder script")
        st.write("Run `python reminder.py` on the laptop. It shows desktop alerts, and "
                 "sends a Telegram message too if you set the two environment variables "
                 "in the README.")
