import streamlit as st
import google.generativeai as genai
import sqlite3
import datetime
import pandas as pd
from fpdf import FPDF
import io
import json
import re
import os
from PIL import Image

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Safal Academy Live", page_icon="🎓", layout="wide")

# --- CUSTOM CSS FOR BETTER UI ---
st.markdown("""
    <style>
    .main-title { text-align: center; color: #1E3A8A; font-weight: bold; font-size: 40px; margin-bottom: -10px;}
    .sub-title { text-align: center; color: #DC2626; font-size: 20px; font-weight: bold; margin-bottom: 30px;}
    .checking-text { text-align: center; color: #047857; font-size: 24px; font-weight: bold; margin-top: 20px;}
    </style>
""", unsafe_allow_html=True)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("safal_academy.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tests (
                    test_code TEXT PRIMARY KEY, class_name TEXT, subject TEXT, 
                    total_marks INTEGER, questions TEXT, answers TEXT, expiry_date TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, test_code TEXT, 
                    student_name TEXT, mobile TEXT, school TEXT, class_name TEXT,
                    obtained_marks INTEGER, eval_data TEXT, timestamp TEXT
                 )''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def get_db_connection():
    return sqlite3.connect("safal_academy.db")

def extract_json(text):
    match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

# --- PDF GENERATORS ---
class StudentPDF(FPDF):
    def header(self):
        self.set_fill_color(30, 58, 138) # Dark Blue
        self.rect(0, 0, 210, 40, 'F')
        self.set_font('Arial', 'B', 24)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'SAFAL ACADEMY LIVE', 0, 1, 'C')
        self.set_font('Arial', 'I', 12)
        self.set_text_color(220, 38, 38) # Redish
        self.cell(0, 10, 'Powered by Ravish Sir', 0, 1, 'C')
        self.ln(10)

def generate_student_pdf(student_data, test_data, eval_json):
    pdf = StudentPDF()
    pdf.add_page()
    
    # Student Info
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    
    info = f"Name: {student_data['name']} | Class: {student_data['class_name']} | Mob: {student_data['mobile']}\n"
    info += f"School: {student_data['school']}\n"
    info += f"Subject: {test_data['subject']} (Code: {test_data['test_code']})"
    pdf.multi_cell(0, 8, info, border=1, fill=True)
    pdf.ln(5)
    
    # Score
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 128, 0)
    pdf.cell(0, 10, f"Score: {eval_json.get('total_obtained_marks', 0)} / {test_data['total_marks']}", 0, 1, 'C')
    pdf.ln(5)
    
    # QA Breakdown
    for qa in eval_json.get('evaluation', []):
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(30, 58, 138)
        pdf.cell(0, 8, f"{qa.get('question_number', 'Q')}: Marks: {qa.get('obtained_marks', 0)}", 0, 1)
        
        pdf.set_font('Arial', '', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, f"Student Answer: {qa.get('student_answer', '')}")
        
        pdf.set_text_color(220, 38, 38)
        pdf.multi_cell(0, 6, f"Cause of Deduction: {qa.get('deduction_cause', 'None')}")
        
        pdf.set_text_color(0, 128, 0)
        pdf.multi_cell(0, 6, f"Ideal Answer: {qa.get('ideal_answer', '')}")
        pdf.ln(5)
        
    return pdf.output(dest='S').encode('latin1')

def generate_teacher_pdf(test_code, test_data, results_df):
    pdf = StudentPDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, f"Rank List - {test_data['subject']} (Code: {test_code})", 0, 1, 'C')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Class: {test_data['class_name']} | Full Marks: {test_data['total_marks']}", 0, 1, 'C')
    pdf.ln(10)
    
    # Table Header
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(20, 10, 'Rank', 1, 0, 'C', True)
    pdf.cell(80, 10, 'Student Name', 1, 0, 'C', True)
    pdf.cell(50, 10, 'Mobile', 1, 0, 'C', True)
    pdf.cell(40, 10, 'Marks', 1, 1, 'C', True)
    
    # Table Rows
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 11)
    
    for idx, row in results_df.iterrows():
        fill = True if idx % 2 == 0 else False
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(20, 10, str(idx + 1), 1, 0, 'C', fill)
        pdf.cell(80, 10, str(row['student_name'])[:30], 1, 0, 'L', fill)
        pdf.cell(50, 10, str(row['mobile']), 1, 0, 'C', fill)
        pdf.cell(40, 10, str(row['obtained_marks']), 1, 1, 'C', fill)
        
    return pdf.output(dest='S').encode('latin1')

# --- MAIN APP ---
st.markdown("<div class='main-title'>SAFAL ACADEMY LIVE</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Powered by Ravish Sir</div>", unsafe_allow_html=True)

# API Key Config
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    api_key = st.sidebar.text_input("🔑 Gemini API Key (Required)", type="password")
    if not api_key:
        st.warning("Please configure Gemini API Key to run evaluation.")

if api_key:
    genai.configure(api_key=api_key)

portal = st.sidebar.radio("Select Portal", ["🧑‍🎓 Student Portal", "👨‍🏫 Teacher Portal"])

# ==========================================
# TEACHER PORTAL
# ==========================================
if portal == "👨‍🏫 Teacher Portal":
    st.sidebar.markdown("---")
    teacher_pass = st.sidebar.text_input("Teacher Password", type="password")
    
    if teacher_pass != "525077":
        st.error("🔒 Please enter correct Teacher Password to access this portal.")
    else:
        st.success("✅ Logged in as Teacher (Ravish Sir)")
        tab1, tab2 = st.tabs(["📝 Create New Test", "📊 Download Reports"])
        
        # --- TAB 1: CREATE TEST ---
        with tab1:
            st.subheader("Publish a New Test")
            with st.form("create_test_form"):
                col1, col2 = st.columns(2)
                t_class = col1.selectbox("Class", [str(i) for i in range(7, 13)])
                t_sub = col2.text_input("Subject Name")
                t_code = col1.text_input("Unique Test Code (e.g., PHY101)")
                t_marks = col2.number_input("Total Marks", min_value=1)
                
                t_expiry = st.date_input("Expiry Date")
                t_time = st.time_input("Expiry Time")
                
                t_questions = st.text_area("Paste All Questions Here", height=150)
                t_answers = st.text_area("Paste Ideal Answer Key Here", height=150)
                
                submit_test = st.form_submit_button("🚀 Publish Test Live")
                
                if submit_test:
                    if t_code and t_sub:
                        conn = get_db_connection()
                        c = conn.cursor()
                        expiry_datetime = f"{t_expiry} {t_time}"
                        try:
                            c.execute("INSERT INTO tests VALUES (?,?,?,?,?,?,?)", 
                                      (t_code, t_class, t_sub, t_marks, t_questions, t_answers, expiry_datetime))
                            conn.commit()
                            st.success(f"Test {t_code} published successfully! It is now live for students.")
                        except sqlite3.IntegrityError:
                            st.error("Test Code already exists! Please use a unique code.")
                        conn.close()
                    else:
                        st.error("Please fill all required fields.")
                        
        # --- TAB 2: REPORTS ---
        with tab2:
            st.subheader("Generate & Download Results")
            conn = get_db_connection()
            tests = pd.read_sql_query("SELECT test_code, class_name, subject, total_marks FROM tests", conn)
            
            if not tests.empty:
                col1, col2 = st.columns(2)
                sel_class = col1.selectbox("Filter by Class", ["All"] + [str(i) for i in range(7, 13)])
                
                filtered_tests = tests if sel_class == "All" else tests[tests['class_name'] == sel_class]
                sel_test = col2.selectbox("Select Test Code", filtered_tests['test_code'].tolist())
                
                if sel_test:
                    results = pd.read_sql_query(f"SELECT * FROM results WHERE test_code='{sel_test}' ORDER BY obtained_marks DESC", conn)
                    test_info = tests[tests['test_code'] == sel_test].iloc[0]
                    
                    if not results.empty:
                        st.dataframe(results[['student_name', 'mobile', 'school', 'obtained_marks', 'timestamp']])
                        
                        col3, col4 = st.columns(2)
                        # Download PDF
                        pdf_bytes = generate_teacher_pdf(sel_test, test_info, results)
                        col3.download_button("📥 Download Colorful Rank PDF", data=pdf_bytes, file_name=f"Ranklist_{sel_test}.pdf", mime="application/pdf")
                        
                        # Download Excel
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            results.drop(columns=['eval_data']).to_excel(writer, index=False, sheet_name="Results")
                        excel_bytes = output.getvalue()
                        col4.download_button("📥 Download Excel Sheet", data=excel_bytes, file_name=f"Data_{sel_test}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        
                    else:
                        st.info("No students have submitted this test yet.")
            else:
                st.info("No tests created yet.")
            conn.close()

# ==========================================
# STUDENT PORTAL
# ==========================================
elif portal == "🧑‍🎓 Student Portal":
    
    # 1. Fetch Active Tests
    conn = get_db_connection()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_tests = pd.read_sql_query(f"SELECT * FROM tests WHERE expiry_date >= '{now_str}'", conn)
    conn.close()
    
    if active_tests.empty:
        st.warning("No active tests available right now. Please check back later.")
    else:
        st.subheader("📋 Exam Submission Form")
        s_class = st.selectbox("Select Your Class", sorted(list(set(active_tests['class_name']))))
        
        class_tests = active_tests[active_tests['class_name'] == s_class]
        
        if class_tests.empty:
            st.info("No tests currently active for your class.")
        else:
            test_options = class_tests.apply(lambda x: f"{x['test_code']} - {x['subject']} (Full Marks: {x['total_marks']})", axis=1).tolist()
            s_test_display = st.selectbox("Select Test", test_options)
            s_test_code = s_test_display.split(" - ")[0]
            
            with st.form("student_details_form"):
                st.write("**Enter Your Details**")
                s_name = st.text_input("Full Name")
                s_mob = st.text_input("Mobile Number (10 digits)")
                s_school = st.text_input("School Name")
                
                st.write("**Upload Answer Sheets (Max 20 pages)**")
                st.info("Please capture clear photos of your handwritten answer sheets.")
                uploaded_images = st.file_uploader("Upload Image Files (JPG/PNG)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                
                submit_btn = st.form_submit_button("📤 Submit for Evaluation")
            
            if submit_btn:
                if not s_name or not s_mob or len(s_mob) != 10 or not s_school:
                    st.error("Please fill all details correctly (Mobile must be 10 digits).")
                elif not uploaded_images:
                    st.error("Please upload at least 1 photo of your answer sheet.")
                elif len(uploaded_images) > 20:
                    st.error("You can upload a maximum of 20 images.")
                else:
                    st.markdown("<div class='checking-text'>⏳ Ravish Sir Checking... Please Wait...</div>", unsafe_allow_html=True)
                    
                    try:
                        # Prepare images for Gemini
                        gemini_images = []
                        for img in uploaded_images:
                            image = Image.open(img)
                            gemini_images.append(image)
                        
                        test_row = class_tests[class_tests['test_code'] == s_test_code].iloc[0]
                        questions = test_row['questions']
                        answers = test_row['answers']
                        total_marks = test_row['total_marks']
                        
                        prompt = f"""
                        You are a strict evaluator. Read the attached handwritten answer sheets.
                        Compare them against this Answer Key:
                        QUESTIONS:
                        {questions}
                        
                        IDEAL ANSWERS / MARKING SCHEME:
                        {answers}
                        
                        Evaluate strictly. Return ONLY a valid JSON object in this exact format:
                        {{
                            "total_obtained_marks": <total marks as integer>,
                            "evaluation": [
                                {{
                                    "question_number": "Q1",
                                    "student_answer": "text read from image",
                                    "obtained_marks": <int>,
                                    "deduction_cause": "why marks cut (or 'None')",
                                    "ideal_answer": "the correct answer context"
                                }}
                            ]
                        }}
                        Ensure valid JSON output without markdown wrapper if possible.
                        """
                        
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content([prompt] + gemini_images)
                        
                        json_str = extract_json(response.text)
                        eval_data = json.loads(json_str)
                        obtained_marks = eval_data.get('total_obtained_marks', 0)
                        
                        # Save to DB
                        conn = get_db_connection()
                        c = conn.cursor()
                        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute("INSERT INTO results (test_code, student_name, mobile, school, class_name, obtained_marks, eval_data, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                                  (s_test_code, s_name, s_mob, s_school, s_class, obtained_marks, json.dumps(eval_data), now))
                        conn.commit()
                        conn.close()
                        
                        st.success(f"✅ Checking Complete! You scored: {obtained_marks} / {total_marks}")
                        
                        # Generate Student PDF
                        student_info = {"name": s_name, "class_name": s_class, "mobile": s_mob, "school": s_school}
                        pdf_bytes = generate_student_pdf(student_info, test_row, eval_data)
                        
                        st.download_button("📥 Download Your Detailed Answer Report (PDF)", data=pdf_bytes, file_name=f"Report_{s_name}.pdf", mime="application/pdf")
                        
                    except Exception as e:
                        st.error(f"❌ Error during evaluation: Make sure images are clear. Error details: {e}")
