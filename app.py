import streamlit as st
import sqlite3
import datetime
import os
import json
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import google.generativeai as genai
from PIL import Image

# ==========================================
# 1. PAGE CONFIG & CUSTOM CSS (Dark Theme)
# ==========================================
st.set_page_config(page_title="Safal Academy Live | Copy Checker", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0d0d0d; color: #ffffff; }
    h1, h2, h3 { color: #ffeb3b; text-shadow: 2px 2px 4px #000000; }
    .stButton>button { background-color: #ff3d00; color: white; border-radius: 8px; font-weight: bold; border: 2px solid #ffeb3b; }
    .stButton>button:hover { background-color: #00e676; border-color: #ffffff; color: black; }
    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stTextArea>div>textarea { background-color: #1a1a1a; color: #00e5ff; border: 1px solid #ff3d00; }
    .branding { text-align: center; color: #00e676; font-size: 24px; font-weight: bold; padding: 10px; margin-bottom: 20px; border-bottom: 2px solid #ffeb3b; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE SETUP (Optimized for Streamlit)
# ==========================================
DB_NAME = "safal_academy.db"

def init_db():
    with sqlite3.connect(DB_NAME, timeout=15) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT, subject TEXT, test_code TEXT UNIQUE,
            total_marks INTEGER, questions TEXT, ideal_answers TEXT, expiry_datetime TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_code TEXT, student_name TEXT, mobile TEXT, school_name TEXT, class_name TEXT,
            obtained_marks REAL, evaluation_json TEXT
        )
        """)
        conn.commit()

init_db()

# ==========================================
# 3. AI CONFIGURATION (Gemini)
# ==========================================
API_KEY = os.environ.get("GEMINI_API_KEY", "") 
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    st.warning("⚠️ API Key not found in Environment Variables! Please add GEMINI_API_KEY in Render.")

model = genai.GenerativeModel('gemini-1.5-flash-latest')

# ==========================================
# 4. PDF GENERATION CLASSES
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", 'B', 20)
        self.set_text_color(255, 61, 0)
        self.cell(0, 10, "SAFAL ACADEMY LIVE", ln=True, align="C")
        self.set_font("Arial", 'I', 12)
        self.set_text_color(0, 230, 118)
        self.cell(0, 10, "Powered by Ravish Sir", ln=True, align="C")
        self.ln(5)

# ==========================================
# 5. TEACHER PORTAL
# ==========================================
def teacher_portal():
    st.markdown('<div class="branding">👨‍🏫 Teacher Portal</div>', unsafe_allow_html=True)
    if "teacher_logged_in" not in st.session_state:
        st.session_state.teacher_logged_in = False

    if not st.session_state.teacher_logged_in:
        pwd = st.text_input("Enter Teacher Password", type="password")
        if st.button("Login"):
            if pwd == "525077":
                st.session_state.teacher_logged_in = True
                st.rerun()
            else:
                st.error("❌ Incorrect Password!")
        return

    if st.button("Logout"):
        st.session_state.teacher_logged_in = False
        st.rerun()

    tab1, tab2 = st.tabs(["📝 Create New Test", "📊 Download Reports"])

    with tab1:
        with st.form("create_test_form"):
            col1, col2 = st.columns(2)
            with col1:
                class_name = st.selectbox("Class", [f"Class {i}" for i in range(7, 13)])
                subject = st.text_input("Subject")
                test_code = st.text_input("Test Code (Unique)")
                total_marks = st.number_input("Total Marks", min_value=1)
            with col2:
                exp_date = st.date_input("Expiry Date")
                exp_time = st.time_input("Expiry Time")
            
            questions = st.text_area("Paste All Questions Here")
            ideal_answers = st.text_area("Paste Ideal Answers / Marking Scheme Here")
            
            if st.form_submit_button("Launch Test"):
                if subject and test_code and questions and ideal_answers:
                    expiry_str = datetime.datetime.combine(exp_date, exp_time).strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        with sqlite3.connect(DB_NAME, timeout=15) as conn:
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO tests (class_name, subject, test_code, total_marks, questions, ideal_answers, expiry_datetime) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                           (class_name, subject, test_code, total_marks, questions, ideal_answers, expiry_str))
                            conn.commit()
                        st.success(f"✅ Test '{test_code}' is now Live until {expiry_str}!")
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Test Code already exists! Choose a different one.")
                    except sqlite3.OperationalError as e:
                        st.error(f"⚠️ Database busy, please try again. ({e})")
                else:
                    st.error("⚠️ Please fill all fields.")

    with tab2:
        with sqlite3.connect(DB_NAME, timeout=15) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT test_code FROM tests")
            tests = [row[0] for row in cursor.fetchall()]
            
        if tests:
            selected_test = st.selectbox("Select Test Code for Report", tests)
            if st.button("Generate Reports"):
                with sqlite3.connect(DB_NAME, timeout=15) as conn:
                    df = pd.read_sql_query(f"SELECT student_name, mobile, school_name, class_name, obtained_marks FROM results WHERE test_code='{selected_test}' ORDER BY obtained_marks DESC", conn)
                
                if not df.empty:
                    df.insert(0, 'Rank', range(1, 1 + len(df)))
                    st.dataframe(df)

                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name="Rank List")
                    st.download_button("📥 Download Excel Sheet", data=output.getvalue(), file_name=f"{selected_test}_RankList.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    
                    pdf = PDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.set_text_color(0, 229, 255)
                    pdf.cell(0, 10, f"Rank List - Test Code: {selected_test}", ln=True, align="C")
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.set_text_color(255, 255, 255)
                    
                    for index, row in df.iterrows():
                        pdf.set_text_color(255, 235, 59)
                        pdf.cell(0, 10, f"Rank {row['Rank']}: {row['student_name']} ({row['school_name']}) - Marks: {row['obtained_marks']}", ln=True)
                    
                    pdf_bytes = pdf.output(dest='S').encode('latin-1', 'replace')
                    st.download_button("📥 Download Colorful PDF", data=pdf_bytes, file_name=f"{selected_test}_Ranks.pdf", mime="application/pdf")
                else:
                    st.warning("No students have submitted this test yet.")
        else:
            st.info("No tests created yet.")

# ==========================================
# 6. STUDENT PORTAL
# ==========================================
def student_portal():
    st.markdown('<div class="branding">🎓 Student Portal</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        student_name = st.text_input("Full Name")
        mobile = st.text_input("Mobile Number (10 digits)", max_chars=10)
    with col2:
        school_name = st.text_input("School Name")
        class_name = st.selectbox("Select Class", [f"Class {i}" for i in range(7, 13)])
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with sqlite3.connect(DB_NAME, timeout=15) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subject, test_code, total_marks, questions, ideal_answers FROM tests WHERE class_name=? AND expiry_datetime > ?", (class_name, now_str))
        active_tests = cursor.fetchall()

    if not active_tests:
        st.info(f"No active tests available for {class_name} at the moment.")
        return

    test_options = {f"{t[0]} (Code: {t[1]})": t for t in active_tests}
    selected_test_label = st.selectbox("Select Active Test", list(test_options.keys()))
    test_data = test_options[selected_test_label]
    
    st.info(f"Subject: {test_data[0]} | Max Marks: {test_data[2]}")
    
    uploaded_files = st.file_uploader("Upload Answer Sheets (Max 20 Pages)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
    
    if st.button("Submit & Check Answer Sheet"):
        if not (student_name and len(mobile) == 10 and school_name):
            st.error("⚠️ Please fill your Name, correct Mobile Number, and School Name.")
            return
        if not uploaded_files:
            st.error("⚠️ Please upload at least one image of your answer sheet.")
            return
        if len(uploaded_files) > 20:
            st.error("⚠️ Maximum 20 pages allowed.")
            return

        with st.spinner("⏳ Ravish Sir Checking... Please Wait..."):
            try:
                images = [Image.open(f) for f in uploaded_files]
                
                prompt = f"""
                You are an expert strict examiner for Safal Academy Live.
                Evaluate the student's handwritten answer sheets against these questions:
                {test_data[3]}
                And this ideal answer key/marking scheme:
                {test_data[4]}
                Max Marks: {test_data[2]}
                
                Respond STRICTLY in valid JSON format:
                {{
                    "total_obtained_marks": <number>,
                    "evaluation": [
                        {{
                            "question_number": <number or string>,
                            "student_answer": "<brief summary of what student wrote>",
                            "obtained_marks": <number>,
                            "cause_of_deduction": "<reason why marks were cut, or 'Perfect' if full marks>",
                            "ideal_answer": "<correct answer concept>"
                        }}
                    ]
                }}
                Do not include markdown tags like ```json in the output.
                """
                
                response = model.generate_content([prompt] + images)
                raw_json = response.text.replace("```json", "").replace("```", "").strip()
                eval_data = json.loads(raw_json)
                
                with sqlite3.connect(DB_NAME, timeout=15) as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO results (test_code, student_name, mobile, school_name, class_name, obtained_marks, evaluation_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (test_data[1], student_name, mobile, school_name, class_name, eval_data['total_obtained_marks'], json.dumps(eval_data)))
                    conn.commit()
                
                st.success(f"✅ Evaluation Complete! You scored {eval_data['total_obtained_marks']} / {test_data[2]}")
                
                pdf = PDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.set_text_color(0, 229, 255)
                pdf.cell(0, 8, f"Name: {student_name} | Class: {class_name}", ln=True)
                pdf.cell(0, 8, f"School: {school_name} | Mobile: {mobile}", ln=True)
                pdf.cell(0, 8, f"Subject: {test_data[0]} | Test Code: {test_data[1]}", ln=True)
                pdf.set_text_color(255, 235, 59)
                pdf.cell(0, 10, f"RESULT: {eval_data['total_obtained_marks']} / {test_data[2]} Marks", ln=True)
                pdf.ln(5)
                
                for item in eval_data.get('evaluation', []):
                    pdf.set_font("Arial", 'B', 12)
                    pdf.set_text_color(255, 61, 0)
                    pdf.multi_cell(0, 8, f"Question {item['question_number']}")
                    
                    pdf.set_font("Arial", '', 11)
                    pdf.set_text_color(0, 0, 0)
                    pdf.multi_cell(0, 6, f"Student Answer: {item['student_answer']}")
                    
                    pdf.set_font("Arial", 'B', 11)
                    pdf.set_text_color(0, 150, 0)
                    pdf.multi_cell(0, 6, f"Obtained Marks: {item['obtained_marks']}")
                    
                    pdf.set_font("Arial", 'I', 11)
                    pdf.set_text_color(200, 0, 0)
                    pdf.multi_cell(0, 6, f"Cause of Deduction: {item['cause_of_deduction']}")
                    
                    pdf.set_font("Arial", '', 11)
                    pdf.set_text_color(0, 0, 150)
                    pdf.multi_cell(0, 6, f"Ideal Answer: {item['ideal_answer']}")
                    pdf.ln(4)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1', 'replace')
                st.download_button("📥 Download Your Detailed Report (PDF)", data=pdf_bytes, file_name=f"{student_name}_Report.pdf", mime="application/pdf")
                
            except Exception as e:
                st.error(f"❌ Error during evaluation: {str(e)}. Please try again or upload clearer photos.")

# ==========================================
# 7. APP ROUTING
# ==========================================
st.sidebar.title("Safal Academy Live")
st.sidebar.markdown("**Powered by Ravish Sir**")
portal_choice = st.sidebar.radio("Select Portal", ["Student Portal", "Teacher Portal"])

if portal_choice == "Teacher Portal":
    teacher_portal()
else:
    student_portal()
