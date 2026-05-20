import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# ================= 1. إعدادات الصفحة =================
st.set_page_config(page_title="Executive Dashboard | Nile University", page_icon="📊", layout="wide")

# متنساش تحط الباسورد الحقيقية بتاعتك
DB_URL = "postgresql://postgres:Finance01017043056@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require"

# ================= 2. دالة جلب البيانات =================
@st.cache_data # الكود ده بيحفظ الداتا في الكاش عشان ميهلكش السيرفر مع كل ريفريش
def load_data():
    engine = create_engine(DB_URL)
    
    # استعلام بيجيب إجمالي الحركات متجمعة حسب التيرم (Spring, Fall, etc.)
    query = """
        SELECT 
            term,
            academic_year,
            COALESCE(SUM(debit), 0) as total_billed,
            COALESCE(SUM(credit), 0) as total_collected,
            (COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0)) as total_outstanding
        FROM transactions
        WHERE term IS NOT NULL
        GROUP BY term, academic_year
    """
    df = pd.read_sql(query, engine)
    
    # دمج التيرم مع السنة عشان يظهروا في الرسومات البيانية بوضوح (مثلاً Spring 2026)
    df['Term_Name'] = df['term'] + " " + df['academic_year'].astype(str)
    return df

# ================= 3. تصميم الواجهة =================
st.title("📊 لوحة المؤشرات المالية للإدارة العليا")
st.markdown("---")

try:
    df = load_data()
    
    if not df.empty:
        # --- قسم الأرقام المجمعة (KPIs) ---
        st.subheader("💡 الملخص المالي العام")
        col1, col2, col3 = st.columns(3)
        
        total_billed = df['total_billed'].sum()
        total_collected = df['total_collected'].sum()
        total_outstanding = df['total_outstanding'].sum()
        
        # حساب نسبة التحصيل
        collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else 0

        # عرض الكروت
        col1.metric("إجمالي المطالبات (Billed)", f"{total_billed:,.0f} EGP")
        col2.metric("إجمالي التحصيلات (Collected)", f"{total_collected:,.0f} EGP")
        col3.metric("المديونيات المتبقية (Outstanding)", f"{total_outstanding:,.0f} EGP", f"نسبة التحصيل: {collection_rate:.1f}%")
        
        st.markdown("---")
        
        # --- قسم الرسومات البيانية ---
        st.subheader("📈 التحليل المالي حسب التيرم الدراسي")
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # رسم بياني: التحصيل مقابل المديونية
            df_melted = df.melt(id_vars=['Term_Name'], value_vars=['total_collected', 'total_outstanding'], 
                                var_name='Type', value_name='Amount')
            
            # تغيير أسماء المتغيرات لعرضها بشكل شيك
            df_melted['Type'] = df_melted['Type'].replace({'total_collected': 'تم تحصيله', 'total_outstanding': 'متبقي (مديونية)'})
            
            fig1 = px.bar(df_melted, x='Term_Name', y='Amount', color='Type', barmode='group',
                          title='مقارنة التحصيل والمديونيات لكل تيرم',
                          labels={'Amount': 'المبلغ (جنيه)', 'Term_Name': 'التيرم الدراسي', 'Type': 'الحالة'},
                          color_discrete_map={'تم تحصيله': '#28a745', 'متبقي (مديونية)': '#dc3545'})
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            # رسم بياني: حجم المطالبات لكل تيرم
            fig2 = px.pie(df, values='total_billed', names='Term_Name', 
                          title='حصة كل تيرم من إجمالي المطالبات المادية', hole=0.4,
                          color_discrete_sequence=px.colors.sequential.Teal)
            st.plotly_chart(fig2, use_container_width=True)

    else:
        st.info("لا توجد بيانات مالية مسجلة حتى الآن.")

except Exception as e:
    st.error(f"⚠️ حدث خطأ أثناء جلب البيانات: {e}")
