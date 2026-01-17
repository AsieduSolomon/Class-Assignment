import streamlit as st
import pandas as pd
import json
import random
from datetime import datetime
from pathlib import Path
import io
import re  # Added for regex validation

# Try to import reportlab, handle gracefully if not available
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    st.error("⚠️ ReportLab not installed. PDF generation will be disabled. Install it with: pip install reportlab")

# ========== CONFIGURATION ==========
ADMIN_PASSWORD = "renewable2026" 
DATA_FILE = "students_data.json"
COURSE_TITLE = "Renewable Energy Systems Lab"
LECTURER_NAME = "Mr. Frank Effah"
DEPARTMENT = "Department of Electrical and Electronics Engineering"

# ========== DATA PERSISTENCE FUNCTIONS ==========
def validate_index_format(index_number):
    """
    Validate that index number follows STUBTECH format
    Format: STUBTECH followed by exactly 6 digits
    Example: STUBTECH220457
    """
    pattern = r'^STUBTECH\d{6}$'  # Fixed: Added closing $ and fixed quote
    return bool(re.match(pattern, index_number))

def load_data():
    """Load student data from JSON file"""
    if Path(DATA_FILE).exists():
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                return pd.DataFrame(data)
        except:
            return pd.DataFrame(columns=['name', 'index_number', 'primary_group', 'subgroup', 'timestamp'])
    return pd.DataFrame(columns=['name', 'index_number', 'primary_group', 'subgroup', 'timestamp'])

def save_data(df):
    """Save student data to JSON file"""
    df.to_json(DATA_FILE, orient='records', indent=2)

# ========== GROUPING LOGIC ==========
def assign_groups(df):
    """
    Assign students to groups randomly but evenly.
    Primary groups: A, B, C, D, E
    Subgroups: 1, 2, 3, 4, 5
    Total: 25 subgroups (A1, A2, A3, A4, A5, B1, B2...E5)
    """
    # Create all possible group combinations
    primary_groups = ['A', 'B', 'C', 'D', 'E']
    subgroups = ['1', '2', '3', '4', '5']
    all_groups = [(p, s) for p in primary_groups for s in subgroups]
    
    # Get unassigned students
    unassigned = df[df['primary_group'].isna() | (df['primary_group'] == '')].copy()
    num_unassigned = len(unassigned)
    
    if num_unassigned == 0:
        return df
    
    # Create balanced assignment
    # Calculate students per subgroup
    students_per_subgroup = num_unassigned // 25
    remainder = num_unassigned % 25
    
    # Create assignment list
    assignments = []
    for i, (primary, sub) in enumerate(all_groups):
        # Add extra student to first 'remainder' groups
        count = students_per_subgroup + (1 if i < remainder else 0)
        assignments.extend([(primary, sub)] * count)
    
    # Shuffle for randomness (with seed for reproducibility if needed)
    random.shuffle(assignments)
    
    # Assign groups
    for idx, (primary, sub) in zip(unassigned.index, assignments):
        df.at[idx, 'primary_group'] = primary
        df.at[idx, 'subgroup'] = sub
    
    return df

# ========== PDF GENERATION ==========
def generate_pdf(df):
    """Generate PDF with all group assignments"""
    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab is not installed. Cannot generate PDF.")
        return None
        
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, 
                           topMargin=30, bottomMargin=30)
    
    # Container for PDF elements
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2e5c8a'),
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )
    
    # Header
    elements.append(Paragraph(COURSE_TITLE, title_style))
    elements.append(Paragraph(DEPARTMENT, styles['Normal']))
    elements.append(Paragraph(f"Lecturer: {LECTURER_NAME}", styles['Normal']))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Group by primary and subgroup
    primary_groups = ['A', 'B', 'C', 'D', 'E']
    subgroups = ['1', '2', '3', '4', '5']
    
    for primary in primary_groups:
        elements.append(Paragraph(f"Group {primary}", heading_style))
        
        for sub in subgroups:
            # Filter students in this subgroup
            group_students = df[
                (df['primary_group'] == primary) & 
                (df['subgroup'] == sub)
            ].sort_values('name')
            
            if len(group_students) > 0:
                # Subgroup header
                elements.append(Paragraph(f"<b>Subgroup {primary}{sub}</b> ({len(group_students)} students)", 
                                        styles['Heading3']))
                
                # Create table data
                table_data = [['#', 'Name', 'Index Number']]
                for i, (_, student) in enumerate(group_students.iterrows(), 1):
                    table_data.append([
                        str(i),
                        student['name'],
                        student['index_number']
                    ])
                
                # Create table
                table = Table(table_data, colWidths=[0.5*inch, 3.5*inch, 2*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
                ]))
                
                elements.append(table)
                elements.append(Spacer(1, 15))
        
        # Page break after each primary group
        if primary != 'E':
            elements.append(PageBreak())
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ========== STREAMLIT APP ==========
def main():
    # Page config
    st.set_page_config(
        page_title="Group Assignment System",
        page_icon="🔋",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Custom CSS for mobile-responsive design
    st.markdown("""
        <style>
        .main {
            padding: 1rem;
        }
        .stButton>button {
            width: 100%;
            background-color: #2e5c8a;
            color: white;
            font-weight: bold;
            border-radius: 5px;
            padding: 0.5rem 1rem;
            border: none;
        }
        .stButton>button:hover {
            background-color: #1f4788;
        }
        .success-box {
            padding: 1rem;
            border-radius: 5px;
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            margin: 1rem 0;
        }
        .error-box {
            padding: 1rem;
            border-radius: 5px;
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            margin: 1rem 0;
        }
        h1 {
            color: #1f4788;
        }
        h2 {
            color: #2e5c8a;
        }
        /* Mobile responsive adjustments */
        @media (max-width: 768px) {
            .stDataFrame {
                font-size: 12px;
            }
            h1 {
                font-size: 24px;
            }
            h2 {
                font-size: 18px;
            }
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'show_admin' not in st.session_state:
        st.session_state.show_admin = False
    
    # Load data
    df = load_data()
    
    # Navigation
    st.title("🔋 Renewable Energy Course")
    st.subheader("Group Assignment System")
    
    # Navigation tabs
    tab1, tab2, tab3 = st.tabs(["📝 Student Registration", "🔍 Check Assignment", "🔐 Admin Panel"])
    
    # ========== TAB 1: STUDENT REGISTRATION ==========
    with tab1:
        st.header("Student Registration")
        st.write("Please enter your details to register for group assignment.")
        
        with st.form("registration_form", clear_on_submit=True):
            name = st.text_input("Full Name*", placeholder="Enter your full name", max_chars=100)
            index_number = st.text_input(
                "Index Number*", 
                placeholder="e.g., STUBTECH220457",
                max_chars=16,
                help="Format: STUBTECH followed by 6 digits"
            ).strip().upper()
            
            # Real-time validation hints
            if index_number:
                if not validate_index_format(index_number):
                    st.warning("⚠️ Invalid format! Index must be: STUBTECH + 6 digits (e.g., STUBTECH220457)")
                elif index_number in df['index_number'].values:
                    st.warning("⚠️ This index number is already registered!")
            
            submitted = st.form_submit_button("Register", use_container_width=True)
            
            if submitted:
                # Validation 1: Check for empty fields
                if not name or not index_number:
                    st.error("⚠️ Please fill in all fields!")
                
                # Validation 2: Check index number format (STUBTECH + 6 digits)
                elif not validate_index_format(index_number):
                    st.error("❌ **Invalid Index Number Format!**")
                    st.info("✅ **Correct format:** STUBTECH followed by exactly 6 digits")
                    st.code("Example: STUBTECH220457", language=None)
                    st.warning(f"Your input: {index_number}")
                
                # Validation 3: Check for duplicate index number
                elif index_number in df['index_number'].values:
                    existing_student = df[df['index_number'] == index_number].iloc[0]
                    st.error(f"❌ **Duplicate Entry Detected!**")
                    st.warning(f"Index number **{index_number}** is already registered to **{existing_student['name']}**")
                    st.info("💡 If this is you, check your group assignment in the 'Check Assignment' tab.")
                
                # Validation 4: Check minimum name length
                elif len(name.strip()) < 3:
                    st.error("❌ Name must be at least 3 characters long!")
                
                # All validations passed - register student
                else:
                    # Add new student
                    new_student = pd.DataFrame([{
                        'name': name.strip(),
                        'index_number': index_number,
                        'primary_group': '',
                        'subgroup': '',
                        'timestamp': datetime.now().isoformat()
                    }])
                    df = pd.concat([df, new_student], ignore_index=True)
                    save_data(df)
                    st.success(f"✅ Registration successful! Welcome, {name}!")
                    st.info("ℹ️ Groups will be assigned by the course administrator. Check your assignment in the 'Check Assignment' tab.")
        
        # Show registration stats
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Registered", len(df))
        with col2:
            assigned = len(df[df['primary_group'] != ''])
            st.metric("Assigned to Groups", assigned)
        with col3:
            unassigned = len(df) - assigned
            st.metric("Pending Assignment", unassigned)
    
    # ========== TAB 2: CHECK ASSIGNMENT ==========
    with tab2:
        st.header("Check Your Group Assignment")
        
        search_index = st.text_input(
            "Enter your Index Number", 
            placeholder="e.g., STUBTECH220457",
            help="Enter your index number in the format: STUBTECH + 6 digits"
        ).strip().upper()
        
        if st.button("Search", use_container_width=True):
            if search_index:
                if not validate_index_format(search_index):
                    st.error("❌ Invalid index number format! Please use: STUBTECH + 6 digits")
                else:
                    student = df[df['index_number'] == search_index]
                    if len(student) > 0:
                        student = student.iloc[0]
                        st.success(f"**Name:** {student['name']}")
                        
                        if student['primary_group'] and student['subgroup']:
                            st.info(f"""
                            ### 📋 Your Assignment
                            **Primary Group:** {student['primary_group']}
                            
                            **Subgroup:** {student['primary_group']}{student['subgroup']}
                            
                            **Full Group ID:** {student['primary_group']}{student['subgroup']}
                            """)
                        else:
                            st.warning("⏳ Groups have not been assigned yet. Please check back later.")
                    else:
                        st.error("❌ Index number not found. Please register first.")
            else:
                st.warning("⚠️ Please enter your index number.")
    
    # ========== TAB 3: ADMIN PANEL ==========
    with tab3:
        if not st.session_state.logged_in:
            st.header("Admin Login")
            
            with st.form("login_form"):
                password = st.text_input("Password", type="password")
                login_btn = st.form_submit_button("Login", use_container_width=True)
                
                if login_btn:
                    if password == ADMIN_PASSWORD:
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error("❌ Incorrect password!")
        
        else:
            # Admin panel
            col1, col2 = st.columns([6, 1])
            with col1:
                st.header("Admin Dashboard")
            with col2:
                if st.button("Logout"):
                    st.session_state.logged_in = False
                    st.rerun()
            
            st.divider()
            
            # Statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Students", len(df))
            with col2:
                assigned = len(df[df['primary_group'] != ''])
                st.metric("Assigned", assigned)
            with col3:
                unassigned = len(df) - assigned
                st.metric("Unassigned", unassigned)
            with col4:
                groups_filled = df[df['primary_group'] != ''].groupby(['primary_group', 'subgroup']).size().count()
                st.metric("Active Subgroups", groups_filled)
            
            st.divider()
            
            # Action buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🎲 Assign Groups", use_container_width=True, type="primary"):
                    if len(df) == 0:
                        st.error("No students to assign!")
                    else:
                        df = assign_groups(df)
                        save_data(df)
                        st.success("✅ Groups assigned successfully!")
                        st.rerun()
            
            with col2:
                if REPORTLAB_AVAILABLE and len(df) > 0 and len(df[df['primary_group'] != '']) > 0:
                    try:
                        pdf_buffer = generate_pdf(df)
                        if pdf_buffer:
                            st.download_button(
                                label="📄 Download PDF",
                                data=pdf_buffer,
                                file_name=f"group_assignments_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"PDF generation failed: {str(e)}")
                elif not REPORTLAB_AVAILABLE:
                    st.button("📄 PDF (Not Available)", disabled=True, use_container_width=True)
                    st.caption("Install reportlab to enable PDF export")
            
            with col3:
                if len(df) > 0:
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📊 Download CSV",
                        data=csv,
                        file_name=f"students_data_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            
            st.divider()
            
            # View all registrations
            st.subheader("All Registrations")
            
            # Search and filter
            search_term = st.text_input("🔍 Search by name or index number")
            
            if len(df) > 0:
                display_df = df.copy()
                
                if search_term:
                    display_df = display_df[
                        display_df['name'].str.contains(search_term, case=False, na=False) |
                        display_df['index_number'].str.contains(search_term, case=False, na=False)
                    ]
                
                # Format for display
                display_df['Group'] = display_df.apply(
                    lambda x: f"{x['primary_group']}{x['subgroup']}" if x['primary_group'] else "Not assigned",
                    axis=1
                )
                
                # Format timestamp for better readability
                display_df['Registration Date'] = display_df['timestamp'].apply(
                    lambda x: datetime.fromisoformat(x).strftime('%Y-%m-%d %H:%M') if pd.notna(x) else 'N/A'
                )
                
                st.dataframe(
                    display_df[['name', 'index_number', 'primary_group', 'subgroup', 'Group', 'Registration Date']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Group distribution
                if len(df[df['primary_group'] != '']) > 0:
                    st.subheader("Group Distribution")
                    
                    group_counts = df[df['primary_group'] != ''].groupby(['primary_group', 'subgroup']).size().reset_index(name='count')
                    group_counts['Group'] = group_counts['primary_group'] + group_counts['subgroup']
                    
                    st.bar_chart(group_counts.set_index('Group')['count'])
            else:
                st.info("No students registered yet.")
            
            # Danger zone
            st.divider()
            st.subheader("⚠️ Danger Zone")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Clear All Assignments", use_container_width=True):
                    df['primary_group'] = ''
                    df['subgroup'] = ''
                    save_data(df)
                    st.warning("All group assignments cleared!")
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Delete All Data", use_container_width=True):
                    confirm = st.checkbox("I confirm I want to delete ALL data")
                    if confirm:
                        if Path(DATA_FILE).exists():
                            Path(DATA_FILE).unlink()
                        st.error("All data deleted!")
                        st.rerun()

if __name__ == "__main__":
    main()

