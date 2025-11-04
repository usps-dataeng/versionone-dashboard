import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="EEB Version One Hours Tracker", layout="wide", page_icon="📊")

CONTRACTOR_FILE = "Contractor File.xlsx"
PROJECT_COLS = ['CDAS-6441', 'EDS-4834', 'EEB-9372', 'UAP-SPM-9442', 'UAP-IV-9443', 'UAPSAL-9402']

@st.cache_data(ttl=10)
def load_contractor_data():
    df = pd.read_excel(CONTRACTOR_FILE)
    df = df[['Contractor Group', 'Names'] + PROJECT_COLS].copy()
    df.columns = ['Contractor Group', 'Owner'] + PROJECT_COLS
    df['Owner'] = df['Owner'].astype(str).str.strip()
    return df

def process_uploaded_file(uploaded_df):
    contractor_df = load_contractor_data()

    uploaded_df['Owner'] = uploaded_df['Owner'].astype(str).str.strip()
    uploaded_df['Status'] = uploaded_df['Status'].astype(str).fillna('Unknown')
    uploaded_df['Sprint'] = uploaded_df['Sprint'].astype(str).str.extract(r'(\d+)').astype(float)
    uploaded_df['Backlog'] = uploaded_df['Backlog'].astype(str).fillna('')
    uploaded_df['Est. Hours'] = pd.to_numeric(uploaded_df['Est. Hours'], errors='coerce').fillna(0)
    uploaded_df['To Do'] = pd.to_numeric(uploaded_df['To Do'], errors='coerce').fillna(0)

    for col in PROJECT_COLS:
        if col not in uploaded_df.columns:
            uploaded_df[col] = 0.0
        else:
            uploaded_df[col] = pd.to_numeric(uploaded_df[col], errors='coerce').fillna(0)

    uploaded_df = uploaded_df.merge(contractor_df[['Owner', 'Contractor Group']], on='Owner', how='left')
    uploaded_df['Contractor Group'] = uploaded_df['Contractor Group'].fillna('Unknown')

    uploaded_df['Completed Hours'] = uploaded_df['Est. Hours'] - uploaded_df['To Do']
    uploaded_df['Progress %'] = ((uploaded_df['Completed Hours'] / uploaded_df['Est. Hours']) * 100).fillna(0).round(1)
    uploaded_df['Total Project Hours'] = uploaded_df[PROJECT_COLS].sum(axis=1)

    return uploaded_df

def get_all_contractors_with_hours(df):
    contractor_df = load_contractor_data()
    hours_by_owner = df.groupby('Owner').agg({
        'Est. Hours': 'sum',
        'Completed Hours': 'sum',
        'To Do': 'sum',
        'Title': 'count'
    }).reset_index()
    hours_by_owner.columns = ['Owner', 'Est. Hours', 'Completed Hours', 'To Do', 'Task Count']

    all_contractors = contractor_df[['Owner', 'Contractor Group']].copy()
    all_contractors = all_contractors.merge(hours_by_owner, on='Owner', how='left')
    all_contractors = all_contractors.fillna(0)

    return all_contractors
    
# --- Streamlit UI ---
st.title("📊 EEB Version One Hours Tracker")
st.markdown("### Data Engineering Team - Sprint Hour Management")

DATA_FILE = "task_quicklist.xlsx"
df = None

# Load from local file if available
if os.path.exists(DATA_FILE):
    try:
        raw_df = pd.read_excel(DATA_FILE)
        df = process_uploaded_file(raw_df)

        # Dynamically populate Planning Level columns with Est. Hours
        for code in PROJECT_COLS:
            df[code] = df.apply(
                lambda row: row["Est. Hours"] - row["To Do"] if row["Planning Level"] == code else 0.0,
                axis=1
            )
    except Exception as e:
        st.error(f"Error loading data file: {str(e)}")
else:
    st.warning("No VersionOne export file found. Please upload one manually below.")
    uploaded_file = st.file_uploader("📤 Upload Version One Export File", type=["xlsx"])
    if uploaded_file:
        try:
            raw_df = pd.read_excel(uploaded_file)
            df = process_uploaded_file(raw_df)

            # Dynamically populate Planning Level columns with Est. Hours
            for code in PROJECT_COLS:
                df[code] = df.apply(
                    lambda row: row["Est. Hours"] - row["To Do"] if row["Planning Level"] == code else 0.0,
                    axis=1
                )

        except Exception as e:
            st.error(f"Error loading uploaded file: {str(e)}")

# Define tabs if data is loaded
if df is not None:
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📈 Dashboard",
        "➕ Add/Edit Hours",
        "📋 Sprint Report",
        "🏢 Project Tracking",
        "👥 Contractor Accountability",
        "📊 Analytics",
        "📂 Backlog Tasks"
    ])

    with tab1:
        st.header("📈 Overview Dashboard")

        if df is not None:
            # Summary metrics
            total_est = df['Est. Hours'].sum()
            total_completed = df['Completed Hours'].sum()
            total_remaining = df['To Do'].sum()
            overall_progress = (total_completed / total_est * 100) if total_est > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Estimated Hours", f"{total_est:,.1f}")
            col2.metric("Completed Hours", f"{total_completed:,.1f}")
            col3.metric("Remaining Hours", f"{total_remaining:,.1f}")
            col4.metric("Overall Progress", f"{overall_progress:.1f}%")

            st.markdown("---")
            
            st.write("Raw Sprint values:", df["Sprint"].dropna().unique())
            st.write("Raw Status values:", df["Status"].dropna().unique())
            st.write("Sample rows:", df[["Sprint", "Status", "Est. Hours", "To Do", "Completed Hours"]].head(10))

            
            # ✅ Insert here
            st.subheader("🔍 Completed Hours Validation")

            # Normalize Sprint and Status columns
            df["Sprint"] = pd.to_numeric(df["Sprint"], errors="coerce")
            df["Status"] = df["Status"].astype(str).str.strip().str.lower()

            # Get available sprints
            available_sprints = sorted(df["Sprint"].dropna().unique(), reverse=True)
            selected_sprint = st.selectbox("Select Sprint", available_sprints)

            # View mode toggle
            view_mode = st.radio("View Mode", ["Current Sprint", "All Sprints"])

            # Filter completed tasks using actual status values
            completed = df[df["Status"] == "completed"]

            # Apply sprint filter if needed
            if view_mode == "Current Sprint":
                completed = completed[completed["Sprint"] == selected_sprint]

            # Display total completed hours
            total_completed = completed["Completed Hours"].sum()
            st.metric("Completed Hours", round(total_completed, 2))

            # Dynamically detect project columns
            project_cols = [col for col in completed.columns if "-" in col]
            display_cols = ["Owner", "Est. Hours", "To Do", "Completed Hours"] + project_cols
            available_cols = [col for col in display_cols if col in completed.columns]

            # Show filtered completed tasks or fallback
            if completed.empty:
                st.warning("No completed tasks found for the selected sprint and view mode.")
            else:
                st.dataframe(completed[available_cols].head(10))            

            # Sprint chart
            st.subheader("Hours by Sprint")
            sprint_summary = df.groupby('Sprint')[['Completed Hours', 'To Do']].sum().reset_index()
            fig_sprint = px.bar(sprint_summary, x='Sprint', y=['Completed Hours', 'To Do'], barmode='stack',
                                color_discrete_map={'Completed Hours': '#00CC96', 'To Do': '#EF553B'})
            st.plotly_chart(fig_sprint, use_container_width=True)

            # Contractor chart
            st.subheader("Hours by Contractor Group")
            contractor_summary = df.groupby('Contractor Group')[['Completed Hours', 'To Do']].sum().reset_index()
            fig_contractor = px.bar(contractor_summary, x='Contractor Group', y=['Completed Hours', 'To Do'], barmode='stack',
                                    color_discrete_map={'Completed Hours': '#00CC96', 'To Do': '#EF553B'})
            st.plotly_chart(fig_contractor, use_container_width=True)

            st.markdown("---")
            st.subheader("Task Progress Details")

            # Filters
            col1, col2, col3, col4, col5 = st.columns(5)
            sprint_filter = col1.multiselect("Sprint", sorted(df['Sprint'].unique()))
            owner_filter = col2.multiselect("Owner", sorted(df['Owner'].unique()))
            status_filter = col3.multiselect("Status", sorted(df['Status'].unique()))
            group_filter = col4.multiselect("Contractor Group", sorted(df['Contractor Group'].unique()))
            project_filter = col5.multiselect("Project (has hours)", PROJECT_COLS)

            filtered_df = df.copy()
            if sprint_filter:
                filtered_df = filtered_df[filtered_df['Sprint'].isin(sprint_filter)]
            if owner_filter:
                filtered_df = filtered_df[filtered_df['Owner'].isin(owner_filter)]
            if status_filter:
                filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
            if group_filter:
                filtered_df = filtered_df[filtered_df['Contractor Group'].isin(group_filter)]
            if project_filter:
                mask = filtered_df[project_filter].gt(0).any(axis=1)
                filtered_df = filtered_df[mask]

            display_df = filtered_df[['Title', 'ID', 'Owner', 'Contractor Group', 'Status', 'Sprint',
                                      'Est. Hours', 'Completed Hours', 'To Do', 'Progress %', 'Total Project Hours']]

            def color_progress(val):
                if val >= 100:
                    return 'background-color: #00CC96; color: white'
                elif val >= 50:
                    return 'background-color: #FFA15A; color: white'
                else:
                    return 'background-color: #EF553B; color: white'

            styled_df = display_df.style.applymap(color_progress, subset=['Progress %'])
            st.dataframe(styled_df, use_container_width=True, height=400)
            
        else:
            st.info("Please upload a Version One Excel file to begin.")


    # --- TAB 2: ➕ Add/Edit Hours ---
    with tab2:
        st.header("➕ Add or Update Task Hours")

        mode = st.radio("Select Mode", ["Add New Task", "Update Existing Task"], horizontal=True)

        contractor_df = load_contractor_data()
        available_owners = sorted(contractor_df['Owner'].unique().tolist())

        if mode == "Add New Task":
            st.subheader("➕ Add New Task")

            col1, col2 = st.columns(2)
            with col1:
                new_title = st.text_input("Task Title*")
                new_id = st.text_input("Task ID*")
                new_owner = st.selectbox("Owner*", options=available_owners + ['Other'])
                if new_owner == 'Other':
                    new_owner = st.text_input("Enter New Owner Name")
                    new_contractor_group = st.text_input("Enter Contractor Group")
                else:
                    new_contractor_group = contractor_df[contractor_df['Owner'] == new_owner]['Contractor Group'].iloc[0] if new_owner in contractor_df['Owner'].values else 'Unknown'
                    st.info(f"Contractor Group: {new_contractor_group}")

                new_status = st.selectbox("Status*", options=sorted(df['Status'].unique()))

            with col2:
                new_est_hours = st.number_input("Estimated Hours*", min_value=0.0, step=0.5, value=0.0)
                new_todo = st.number_input("To Do Hours*", min_value=0.0, step=0.5, value=0.0)
                new_backlog = st.text_input("Backlog", value="")

                # Ensure Sprint column is numeric
                sprint_values = pd.to_numeric(df["Sprint"], errors="coerce").dropna().unique().tolist()
                sprint_options = sorted(sprint_values)
                sprint_options.append("Other")

                new_sprint = st.selectbox("Sprint*", options=sprint_options)

                if new_sprint == "Other":
                    new_sprint = st.text_input("Enter New Sprint Name")

            st.subheader("Project Hours Allocation")
            project_cols = st.columns(3)
            new_project_hours = {}
            for idx, proj in enumerate(PROJECT_COLS):
                with project_cols[idx % 3]:
                    new_project_hours[proj] = st.number_input(proj, min_value=0.0, step=0.5, value=0.0, key=f"new_{proj}")

            if st.button("➕ Add Task", type="primary"):
                if new_title and new_id and new_owner and new_status and new_sprint:
                    new_row_data = {
                        'Title': new_title,
                        'ID': new_id,
                        'Owner': new_owner,
                        'Contractor Group': new_contractor_group,
                        'Status': new_status,
                        'Est. Hours': new_est_hours,
                        'To Do': new_todo,
                        'Backlog': new_backlog,
                        'Sprint': new_sprint
                    }
                    new_row_data.update(new_project_hours)
                    new_row = pd.DataFrame([new_row_data])
                    new_row = process_uploaded_file(new_row)
                    df = pd.concat([df, new_row], ignore_index=True)
                    st.success("Task added successfully!")
                    st.rerun()
                else:
                    st.error("Please fill in all required fields marked with *")

        else:
            st.subheader("✏️ Update Existing Task")

            task_titles = df['Title'].tolist()
            selected_task = st.selectbox("Select Task to Update", options=task_titles)

            if selected_task:
                task_idx = df[df['Title'] == selected_task].index[0]
                task_data = df.loc[task_idx]

                col1, col2 = st.columns(2)
                with col1:
                    upd_owner = st.selectbox("Update Owner", options=available_owners, index=available_owners.index(task_data['Owner']) if task_data['Owner'] in available_owners else 0)
                    upd_contractor_group = contractor_df[contractor_df['Owner'] == upd_owner]['Contractor Group'].iloc[0] if upd_owner in contractor_df['Owner'].values else task_data['Contractor Group']
                    st.info(f"Contractor Group: {upd_contractor_group}")
                    upd_status = st.selectbox("Update Status", options=sorted(df['Status'].unique()), index=sorted(df['Status'].unique().tolist()).index(task_data['Status']))

                with col2:
                    upd_est_hours = st.number_input("Update Estimated Hours", min_value=0.0, step=0.5, value=float(task_data['Est. Hours']))
                    upd_todo = st.number_input("Update To Do Hours", min_value=0.0, step=0.5, value=float(task_data['To Do']))
                    upd_sprint = st.selectbox("Update Sprint", options=sorted(df['Sprint'].unique()), index=sorted(df['Sprint'].unique().tolist()).index(task_data['Sprint']))

                st.subheader("Update Project Hours")
                project_cols = st.columns(3)
                upd_project_hours = {}
                for idx, proj in enumerate(PROJECT_COLS):
                    with project_cols[idx % 3]:
                        current_val = float(task_data[proj]) if proj in task_data.index else 0.0
                        upd_project_hours[proj] = st.number_input(proj, min_value=0.0, step=0.5, value=current_val, key=f"upd_{proj}")

                col_update, col_delete = st.columns([1, 1])
                with col_update:
                    if st.button("💾 Update Task", type="primary"):
                        df.loc[task_idx, 'Owner'] = upd_owner
                        df.loc[task_idx, 'Contractor Group'] = upd_contractor_group
                        df.loc[task_idx, 'Status'] = upd_status
                        df.loc[task_idx, 'Est. Hours'] = upd_est_hours
                        df.loc[task_idx, 'To Do'] = upd_todo
                        df.loc[task_idx, 'Sprint'] = upd_sprint
                        for proj, val in upd_project_hours.items():
                            df.loc[task_idx, proj] = val
                        df = process_uploaded_file(df)
                        st.success("Task updated successfully!")
                        st.rerun()

                with col_delete:
                    if st.button("🗑️ Delete Task", type="secondary"):
                        df = df.drop(task_idx).reset_index(drop=True)
                        st.success("Task deleted successfully!")
                        st.rerun()

    # --- TAB 3: 📋 Sprint Report ---
    with tab3:
        st.header("📋 Sprint Report")

        sprints = sorted(df['Sprint'].unique(), reverse=True)
        selected_sprint = st.selectbox("Select Sprint for Report", options=sprints)

        sprint_df = df[df['Sprint'] == selected_sprint]

        sprint_est = sprint_df['Est. Hours'].sum()
        sprint_completed = sprint_df['Completed Hours'].sum()
        sprint_remaining = sprint_df['To Do'].sum()
        sprint_progress = (sprint_completed / sprint_est * 100) if sprint_est > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Estimated", f"{sprint_est:,.1f}h")
        col2.metric("Completed", f"{sprint_completed:,.1f}h")
        col3.metric("Remaining", f"{sprint_remaining:,.1f}h")
        col4.metric("Progress", f"{sprint_progress:.1f}%")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Status Breakdown")
            status_summary = sprint_df.groupby('Status')['Est. Hours'].sum().reset_index()
            fig_status = px.pie(status_summary, values='Est. Hours', names='Status', hole=0.4)
            st.plotly_chart(fig_status, use_container_width=True)

        with col2:
            st.subheader("Contractor Group Breakdown")
            contractor_sprint = sprint_df.groupby('Contractor Group').agg({
                'Est. Hours': 'sum',
                'Completed Hours': 'sum',
                'To Do': 'sum'
            }).reset_index().sort_values('Est. Hours', ascending=False)

            fig_contractor_sprint = go.Figure()
            fig_contractor_sprint.add_trace(go.Bar(name='Completed', y=contractor_sprint['Contractor Group'], x=contractor_sprint['Completed Hours'], orientation='h', marker_color='#00CC96'))
            fig_contractor_sprint.add_trace(go.Bar(name='To Do', y=contractor_sprint['Contractor Group'], x=contractor_sprint['To Do'], orientation='h', marker_color='#EF553B'))
            fig_contractor_sprint.update_layout(barmode='stack', height=400, xaxis_title="Hours", yaxis_title="Contractor Group")
            st.plotly_chart(fig_contractor_sprint, use_container_width=True)

        st.markdown("---")
        st.subheader(f"📋 {selected_sprint} - Detailed Task List")

        report_df = sprint_df[['Title', 'ID', 'Owner', 'Contractor Group', 'Status', 'Est. Hours', 'Completed Hours', 'To Do', 'Progress %'] + PROJECT_COLS].sort_values('Contractor Group')
        st.dataframe(report_df, use_container_width=True, height=400)

        st.download_button(
            label="📥 Download Sprint Report (CSV)",
            data=report_df.to_csv(index=False).encode('utf-8'),
            file_name=f"{selected_sprint}_report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    # --- TAB 4: 🏢 Project Tracking ---
    with tab4:
        st.header("🏢 Project Tracking")

        total_project_hours = df['Total Project Hours'].sum()
        tasks_with_projects = len(df[df['Total Project Hours'] > 0])
        total_tasks = len(df)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Project Hours", f"{total_project_hours:,.1f}")
        col2.metric("Tasks with Projects", tasks_with_projects)
        col3.metric("Total Tasks", total_tasks)

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Hours by Project")
            project_summary = df[PROJECT_COLS].sum().reset_index()
            project_summary.columns = ['Project', 'Hours']
            project_summary = project_summary[project_summary['Hours'] > 0].sort_values('Hours', ascending=False)

            if not project_summary.empty:
                fig_proj = px.bar(project_summary, x='Project', y='Hours', color='Hours',
                                  color_continuous_scale='Blues', height=400)
                st.plotly_chart(fig_proj, use_container_width=True)
            else:
                st.info("No project hours recorded yet")

        with col2:
            st.subheader("Project Distribution")
            if not project_summary.empty:
                fig_pie = px.pie(project_summary, values='Hours', names='Project', hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No project hours recorded yet")

        st.markdown("---")
        st.subheader("Project Hours by Sprint")

        project_by_sprint = df.groupby('Sprint')[PROJECT_COLS].sum().reset_index()
        project_by_sprint = project_by_sprint.sort_values('Sprint')

        fig_proj_sprint = go.Figure()
        for proj in PROJECT_COLS:
            if project_by_sprint[proj].sum() > 0:
                fig_proj_sprint.add_trace(go.Bar(name=proj, x=project_by_sprint['Sprint'], y=project_by_sprint[proj]))

        fig_proj_sprint.update_layout(barmode='stack', height=400, xaxis_title="Sprint", yaxis_title="Hours")
        st.plotly_chart(fig_proj_sprint, use_container_width=True)

        st.markdown("---")
        st.subheader("Detailed Project Allocation")

        selected_project = st.selectbox("Select Project to View Details", options=PROJECT_COLS)
        project_tasks = df[df[selected_project] > 0][['Title', 'ID', 'Owner', 'Contractor Group', 'Sprint', 'Status',
                                                      selected_project, 'Est. Hours', 'Progress %']].sort_values(selected_project, ascending=False)

        if not project_tasks.empty:
            st.dataframe(project_tasks, use_container_width=True, height=400)

            col1, col2 = st.columns(2)
            col1.metric(f"Total {selected_project} Hours", f"{project_tasks[selected_project].sum():,.1f}")
            col2.metric("Number of Tasks", len(project_tasks))
        else:
            st.info(f"No tasks allocated to {selected_project} yet")

    # --- TAB 5: 👥 Contractor Accountability ---
    with tab5:
        st.header("👥 Contractor Accountability")

        all_contractors = get_all_contractors_with_hours(df)

        total_contractors = len(all_contractors)
        active_contractors = len(all_contractors[all_contractors['Task Count'] > 0])
        inactive_contractors = total_contractors - active_contractors
        activity_rate = (active_contractors / total_contractors * 100) if total_contractors > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Contractors", total_contractors)
        col2.metric("Active (with hours)", active_contractors)
        col3.metric("Inactive (no hours)", inactive_contractors)
        col4.metric("Activity Rate", f"{activity_rate:.1f}%")

        st.markdown("---")

        filter_group = st.multiselect("Filter by Contractor Group", options=sorted(all_contractors['Contractor Group'].unique()))
        show_inactive = st.checkbox("Show only inactive contractors", value=False)

        filtered_contractors = all_contractors.copy()
        if filter_group:
            filtered_contractors = filtered_contractors[filtered_contractors['Contractor Group'].isin(filter_group)]
        if show_inactive:
            filtered_contractors = filtered_contractors[filtered_contractors['Task Count'] == 0]

        st.subheader("All Contractors Status")

        def highlight_inactive(row):
            if row['Task Count'] == 0:
                return ['background-color: #ffcccb'] * len(row)
            return [''] * len(row)

        styled_contractors = filtered_contractors.style.apply(highlight_inactive, axis=1)
        st.dataframe(styled_contractors, use_container_width=True, height=500)

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Contractors by Group")
            group_counts = all_contractors.groupby('Contractor Group').agg({
                'Owner': 'count',
                'Task Count': lambda x: (x > 0).sum()
            }).reset_index()
            group_counts.columns = ['Contractor Group', 'Total Contractors', 'Active Contractors']
            group_counts['Inactive'] = group_counts['Total Contractors'] - group_counts['Active Contractors']

            fig_group = go.Figure()
            fig_group.add_trace(go.Bar(name='Active', x=group_counts['Contractor Group'], y=group_counts['Active Contractors'], marker_color='#00CC96'))
            fig_group.add_trace(go.Bar(name='Inactive', x=group_counts['Contractor Group'], y=group_counts['Inactive'], marker_color='#EF553B'))
            fig_group.update_layout(barmode='stack', height=400)
            st.plotly_chart(fig_group, use_container_width=True)

        with col2:
            st.subheader("Top Contributors")
            top_contributors = all_contractors[all_contractors['Task Count'] > 0].nlargest(10, 'Est. Hours')
            fig_top = px.bar(top_contributors, x='Owner', y='Est. Hours', color='Contractor Group', height=400)
            st.plotly_chart(fig_top, use_container_width=True)

        st.download_button(
            label="📥 Download Contractor Report (CSV)",
            data=filtered_contractors.to_csv(index=False).encode('utf-8'),
            file_name=f"contractor_accountability_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    # --- TAB 6: 📊 Analytics & Trends ---
    with tab6:
        st.header("📊 Analytics & Trends")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Sprint Velocity Trend")
            sprint_velocity = df.groupby('Sprint')['Completed Hours'].sum().reset_index().sort_values('Sprint')
            fig_velocity = px.line(sprint_velocity, x='Sprint', y='Completed Hours', markers=True,
                                   line_shape='spline', height=400)
            fig_velocity.update_traces(line_color='#00CC96', line_width=3)
            st.plotly_chart(fig_velocity, use_container_width=True)

        with col2:
            st.subheader("Task Status Distribution")
            status_dist = df.groupby('Status').size().reset_index(name='Count')
            fig_status_dist = px.bar(status_dist, x='Status', y='Count', color='Status', height=400)
            st.plotly_chart(fig_status_dist, use_container_width=True)

        st.markdown("---")
        st.subheader("Top 10 Tasks by Hours")

        top_tasks = df.nlargest(10, 'Est. Hours')[['Title', 'Owner', 'Contractor Group', 'Sprint',
                                                   'Est. Hours', 'Completed Hours', 'To Do',
                                                   'Progress %', 'Total Project Hours']]
        st.dataframe(top_tasks, use_container_width=True)

        st.markdown("---")
        st.subheader("Contractor Group Performance")

        contractor_perf = df.groupby('Contractor Group').agg({
            'Title': 'count',
            'Est. Hours': 'sum',
            'Completed Hours': 'sum',
            'To Do': 'sum',
            'Total Project Hours': 'sum'
        }).reset_index()
        contractor_perf.columns = ['Contractor Group', 'Task Count', 'Total Est. Hours',
                                   'Completed Hours', 'Remaining Hours', 'Project Hours']
        contractor_perf['Completion Rate %'] = ((contractor_perf['Completed Hours'] /
                                                 contractor_perf['Total Est. Hours']) * 100).round(1)
        contractor_perf = contractor_perf.sort_values('Completed Hours', ascending=False)

        st.dataframe(contractor_perf, use_container_width=True)
      
    # --- TAB 7: 📂 Backlog Tasks ---
    with tab7:
        st.header("📂 Backlog Tasks")

        backlog_df = df[df['Backlog'].notna() & (df['Backlog'].str.strip() != '')]

        if backlog_df.empty:
            st.info("No backlog tasks found.")
        else:
            st.dataframe(backlog_df[['Title', 'ID', 'Owner', 'Contractor Group', 'Status', 'Sprint',
                                     'Backlog', 'Est. Hours', 'To Do', 'Completed Hours', 'Progress %']],
                         use_container_width=True, height=400)


st.markdown("---")
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | EEB Data Engineering Team")
