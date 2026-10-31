import streamlit as st
import google.generativeai as genai
import tempfile
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AI Copy Checker Bot", page_icon="📝", layout="wide")

st.title("📝 AI Copy Checker Bot (Powered by Gemini)")
st.markdown("Upload student's answer sheet (PDF) and provide the answer key to get automated evaluation.")

# --- API KEY CONFIGURATION ---
# Pehle environment variable se key lene ki koshish karega (Render ke liye)
api_key = os.environ.get("GEMINI_API_KEY")

# Agar environment variable me key nahi hai, tabhi sidebar me option dikhayega
if not api_key:
    st.sidebar.header("Configuration")
    api_key = st.sidebar.text_input("Enter Google Gemini API Key", type="password")
    st.sidebar.markdown("[Get your free API key here](https://aistudio.google.com/app/apikey)")

if not api_key:
    st.warning("Please configure your Gemini API Key in Render Environment Variables or enter it in the sidebar.")
    st.stop()

# Configure the API key
genai.configure(api_key=api_key)

# --- MAIN APP LAYOUT ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Answer Key & Instructions")
    answer_key = st.text_area(
        "Paste the Marking Scheme or Answer Key here:",
        height=300,
        placeholder="Example: Q1. Definition of gravity (2 marks), Q2. Formula of Force = m*a (3 marks)..."
    )

with col2:
    st.subheader("2. Upload Answer Sheet")
    uploaded_file = st.file_uploader("Upload Student's Copy (PDF only)", type=["pdf"])

# --- EVALUATION LOGIC ---
if st.button("Evaluate Copy", type="primary", use_container_width=True):
    if not answer_key:
        st.error("Please provide the answer key/marking scheme.")
    elif not uploaded_file:
        st.error("Please upload a PDF answer sheet.")
    else:
        with st.spinner("Bot is evaluating the copy... Please wait..."):
            try:
                # Save the uploaded file temporarily so Gemini can access it
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                    temp_pdf.write(uploaded_file.getvalue())
                    temp_pdf_path = temp_pdf.name

                # Upload file to Google Gemini's servers for processing
                gemini_file = genai.upload_file(temp_pdf_path, mime_type="application/pdf")
                
                # Setup the Gemini 1.5 Flash model
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # The strict prompt for the AI examiner
                system_prompt = f"""
                You are a strict, fair, and highly accurate exam evaluator.
                I have uploaded a student's answer sheet (PDF) and provided the official Answer Key below.
                
                Your task is to:
                1. Read the student's handwritten/typed answers from the document.
                2. Compare them against the provided Answer Key.
                3. Assign marks for each question based on accuracy.
                4. Provide a total score at the end.
                5. Give brief constructive feedback on where the student lost marks.
                
                Answer Key / Marking Scheme:
                {answer_key}
                
                Please output the evaluation in a clear, well-structured format (Markdown). Include Question Number, Marks Awarded, and Remarks.
                """
                
                # Call the API
                response = model.generate_content([system_prompt, gemini_file])
                
                # Display the result
                st.success("Evaluation Complete!")
                st.subheader("📊 Evaluation Report")
                st.markdown(response.text)
                
                # Clean up the file from Gemini servers and local temp folder
                genai.delete_file(gemini_file.name)
                os.remove(temp_pdf_path)
                
            except Exception as e:
                st.error(f"An error occurred during evaluation: {e}")
