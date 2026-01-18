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
BACKUP_FILE = "students_data_backup.json"
COURSE_TITLE = "Renewable Energy Systems Lab"
LECTURER_NAME = "Mr. Frank Effah"
DEPARTMENT = "Department of Electrical and Electronics Engineering"

# ========== EMERGENCY RECOVERY FUNCTIONS ==========
def check_data_exists():
    """Check if data file exists and is valid"""
    if not Path(DATA_FILE).exists():
        return False, "❌ Data file does not exist"
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            if len(data) == 0:
                return False, "⚠️ Data file exists but is empty"
            return True, f"✅ Data file exists with {len(data)} records"
    except:
        return False, "❌ Data file is corrupted or invalid"

def search_for_backups():
    """Search for backup files"""
    backup_files = []
    possible_files = [
        DATA_FILE,
        BACKUP_FILE,
        "students_data_old.json",
        "data.json",
        "backup.json",
        ".streamlit/students_data.json"
    ]
    
    for file in possible_files:
        if Path(file).exists():
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                backup_files.append((file, len(data)))
            except:
                backup_files.append((file, "Corrupted"))
    
    return backup_files

def create_backup():
    """Create a backup of current data"""
    if Path(DATA_FILE).exists():
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_name, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Also update the main backup file
            with open(BACKUP_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, backup_name
        except Exception as e:
            return False, str(e)
    return False, "No data to backup"

# ========== DATA PERSISTENCE FUNCTIONS ==========
def validate_index_format(index_number):
    """
    Validate that index number follows STUBTECH format
    Format: STUBTECH followed by exactly 6 digits
    Example: STUBTECH220457
    """
    pattern = r'^STUBTECH\d{6}$'
    return bool(re.match(pattern, index_number))

def load_data():
    """Load student data from JSON file"""
    if Path(DATA_FILE).exists():
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                return pd.DataFrame(data)
        except:
            # Try to load from backup
            if Path(BACKUP_FILE).exists():
                try:
                    with open(BACKUP_FILE, 'r') as f:
                        data = json.load(f)
                        return pd.DataFrame(data)
                except:
                    pass
            return pd.DataFrame(columns=['name', 'index_number', 'primary_group', 'subgroup', 'timestamp'])
    return pd.DataFrame(columns=['name', 'index_number', 'primary_group', 'subgroup', 'timestamp'])

def save_data(df):
    """Save student data to JSON file"""
    # First create backup
    if Path(DATA_FILE).exists():
        create_backup()
    
    # Save new data
    df.to_json(DATA_FILE, orient='records', indent=2)

# ========== GROUPING LOGIC (FIXED) ==========
def assign_groups(df):
    """
    Assign students to groups randomly but evenly.
    Primary groups: A, B, C, D, E
    Subgroups: 1, 2, 3, 4, 5
    Maximum 8 students per subgroup
    Total: 25 subgroups (A1, A2, A3, A4, A5, B1, B2...E5)
    """
    # Create all possible group combinations (fixed 25)
    primary_groups = ['A', 'B', 'C', 'D', 'E']
    subgroups = ['1', '2', '3', '4', '5']
    all_groups = [(p, s) for p in primary_groups for s in subgroups]
    
    # Get unassigned students
    unassigned = df[df['primary_group'].isna() | (df['primary_group'] == '')].copy()
    num_unassigned = len(unassigned)
    
    if num_unassigned == 0:
        return df
    
    # FIXED: Maximum 8 students per subgroup
    STUDENTS_PER_SUBGROUP = 8
    MAX_STUDENTS = len(all_groups) * STUDENTS_PER_SUBGROUP  # 200
    
    # Warning if exceeding capacity
    if num_unassigned > MAX_STUDENTS:
        st.warning(f"⚠️ Warning: {num_unassigned} students registered, but only {MAX_STUDENTS} can be assigned to groups (max 8 per group). {num_unassigned - MAX_STUDENTS} students will remain unassigned.")
        # Only assign first 200 students
        unassigned = unassigned.head(MAX_STUDENTS)
        num_unassigned = MAX_STUDENTS
    
    # Create perfectly balanced assignment
    students_assigned = 0
    assignments = []
    
    for i, (primary, sub) in enumerate(all_groups):
        if students_assigned >= num_unassigned:
            break
        
        # Calculate students for this group (evenly distributed)
        remaining_students = num_unassigned - students_assigned
        remaining_groups = len(all_groups) - i
        
        # Distribute evenly: base amount + 1 for first few groups if there's remainder
        base_per_group = remaining_students // remaining_groups
        extra = 1 if i < (remaining_students % remaining_groups) else 0
        students_for_group = min(base_per_group + extra, STUDENTS_PER_SUBGROUP)
        
        assignments.extend([(primary, sub)] * students_for_group)
        students_assigned += students_for_group
    
    # Shuffle for randomness
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
        .emergency-box {
            padding: 1rem;
            border-radius: 5px;
            background-color: #fff3cd;
            border: 2px solid #ffc107;
            color: #856404;
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
    
    # Check data status immediately
    data_status, data_message = check_data_exists()
    
    # Load data
    df = load_data()
    
    # Navigation
    st.title("🔋 Renewable Energy Course")
    st.subheader("Group Assignment System")
    
    # Navigation tabs - REMOVED RECOVERY TAB
    tab1, tab2, tab3 = st.tabs(["📝 Student Registration", "🔍 Check Assignment", "🔐 Admin Panel"])
    
    # ========== TAB 1: STUDENT REGISTRATION ==========
    with tab1:
        st.header("Student Registration")
        
        # Emergency notice if no data (only show to admin)
        if len(df) == 0 and st.session_state.logged_in:
            st.warning("⚠️ **Notice:** The database appears to be empty. Please use Recovery Tools in Admin Panel.")
        
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
                # Show data status
                status_icon = "✅" if data_status else "❌"
                st.caption(f"{status_icon} Data Status: {data_message}")
            with col2:
                if st.button("Logout"):
                    st.session_state.logged_in = False
                    st.rerun()
            
            st.divider()
            
            # ========== MAIN ADMIN DASHBOARD ==========
            
            # Backup button at the top
            if st.button("💾 Create Backup Now", use_container_width=True):
                success, message = create_backup()
                if success:
                    st.success(f"✅ Backup created: {message}")
                else:
                    st.error(f"❌ Backup failed: {message}")
            
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
            st.subheader("Group Management")
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
            
            # ========== RECOVERY TOOLS (INSIDE ADMIN PANEL) ==========
            with st.expander("🚨 **Emergency Recovery Tools**", expanded=False):
                st.warning("Use these tools only if you've lost data or need to recover from backup.")
                
                # Check current status
                status, message = check_data_exists()
                st.info(f"**Current Status:** {message}")
                
                # Search for backups
                st.subheader("🔍 Search for Backups")
                if st.button("Scan for Backup Files", key="scan_backups"):
                    backups = search_for_backups()
                    if backups:
                        st.success(f"Found {len(backups)} backup file(s):")
                        for file, count in backups:
                            st.write(f"- **{file}**: {count} records")
                            
                            # Option to restore from each backup
                            with st.expander(f"Restore from {file}", expanded=False):
                                try:
                                    with open(file, 'r') as f:
                                        backup_data = json.load(f)
                                    st.write(f"Contains {len(backup_data)} records")
                                    if st.button(f"Restore from {file}", key=f"restore_{file}"):
                                        with open(DATA_FILE, 'w') as f:
                                            json.dump(backup_data, f, indent=2)
                                        st.success(f"✅ Restored from {file}!")
                                        st.rerun()
                                except:
                                    st.error(f"Cannot read {file}")
                    else:
                        st.error("No backup files found!")
                
                # Upload backup file
                st.subheader("📤 Upload Backup File")
                uploaded_file = st.file_uploader("Upload a JSON backup file", type=['json'], key="upload_backup")
                
                if uploaded_file:
                    try:
                        backup_data = json.load(uploaded_file)
                        st.success(f"✅ File loaded: {len(backup_data)} records")
                        
                        # Preview
                        preview_df = pd.DataFrame(backup_data)
                        st.dataframe(preview_df.head())
                        
                        if st.button("💾 Restore from Uploaded File", key="restore_upload"):
                            with open(DATA_FILE, 'w') as f:
                                json.dump(backup_data, f, indent=2)
                            st.success("✅ Data restored successfully!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error reading file: {str(e)}")
                
                # Manual data entry (emergency)
                st.subheader("🆕 Manual Data Entry (Emergency)")
                st.write("If you have a list of students, enter them manually:")
                
                with st.form("manual_entry"):
                    manual_data = st.text_area(
                        "Enter student data (one per line)",
                        placeholder="STUBTECH220001, John Doe\nSTUBTECH220002, Jane Smith",
                        height=200,
                        help="Format: INDEX_NUMBER, FULL_NAME"
                    )
                    
                    if st.form_submit_button("Add Students"):
                        lines = manual_data.strip().split('\n')
                        new_students = []
                        
                        for line in lines:
                            if ',' in line:
                                parts = line.split(',', 1)
                                if len(parts) == 2:
                                    index_num = parts[0].strip().upper()
                                    name = parts[1].strip()
                                    
                                    if validate_index_format(index_num):
                                        new_students.append({
                                            'name': name,
                                            'index_number': index_num,
                                            'primary_group': '',
                                            'subgroup': '',
                                            'timestamp': datetime.now().isoformat()
                                        })
                        
                        if new_students:
                            # Load current data
                            current_df = load_data()
                            new_df = pd.DataFrame(new_students)
                            
                            # Combine and save
                            combined_df = pd.concat([current_df, new_df], ignore_index=True)
                            save_data(combined_df)
                            st.success(f"✅ Added {len(new_students)} new students!")
                            st.rerun()
                        else:
                            st.error("No valid student data found.")
                
                # Direct JSON editor
                st.subheader("✏️ Direct JSON Editor")
                if Path(DATA_FILE).exists():
                    with open(DATA_FILE, 'r') as f:
                        json_content = f.read()
                    
                    edited_json = st.text_area("Edit JSON directly", json_content, height=300, key="json_editor")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Save JSON", key="save_json"):
                            try:
                                # Validate JSON
                                json.loads(edited_json)
                                with open(DATA_FILE, 'w') as f:
                                    f.write(edited_json)
                                st.success("✅ JSON saved successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Invalid JSON: {str(e)}")
                    
                    with col2:
                        st.download_button(
                            label="📥 Download Current JSON",
                            data=json_content,
                            file_name="students_data_backup.json",
                            mime="application/json",
                            key="download_json"
                        )
                else:
                    st.info("No JSON file exists yet. Create one by registering students or uploading a backup.")
            
            st.divider()
            
            # ========== VIEW ALL REGISTRATIONS ==========
            st.subheader("All Registrations")
            
            # Search and filter
            search_term = st.text_input("🔍 Search by name or index number", key="search_admin")
            
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
            
            # ========== DANGER ZONE ==========
            st.divider()
            st.subheader("⚠️ Danger Zone")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Clear All Assignments", use_container_width=True, key="clear_assign"):
                    df['primary_group'] = ''
                    df['subgroup'] = ''
                    save_data(df)
                    st.warning("All group assignments cleared!")
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Delete All Data", use_container_width=True, key="delete_all"):
                    confirm = st.checkbox("I confirm I want to delete ALL data", key="confirm_delete")
                    if confirm:
                        if Path(DATA_FILE).exists():
                            Path(DATA_FILE).unlink()
                        st.error("All data deleted!")
                        st.rerun()

if __name__ == "__main__":
    main()
