import io
import re
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='مقارنة الإجازات 2024 و2025', page_icon='', layout='wide')
st.markdown('''<style>html,body,[class*="css"]{direction:rtl} .stMetric{text-align:right}</style>''', unsafe_allow_html=True)
st.title(' لوحة مقارنة الإجازات | 2024 مقابل 2025')
st.caption('')

FIELDS_2024 = {'رقم الموظف':'employee_id','اسم الموظف':'employee_name','مكان العمل':'entity','عدد الايام':'days'}
FIELDS_2025 = {'رقم الموظف':'employee_id','اسم الموظف':'employee_name','اسم الدائرة':'entity','عدد الايام':'days'}

def norm(s):
    s=str(s).strip().replace('ـ','').replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ة','ه').replace('ى','ي')
    return re.sub(r'\s+', ' ', s).lower()

def read_file(file, year):
    if file.name.lower().endswith('.csv'):
        file.seek(0)
        try: return pd.read_csv(file, encoding='utf-8-sig')
        except UnicodeDecodeError:
            file.seek(0); return pd.read_csv(file, encoding='cp1256')
    file.seek(0)
    if year == 2024:
        sheets = pd.read_excel(file, sheet_name=None)
        if len(sheets) < 2:
            st.warning('ملف 2024 يحتوي على أقل من شيتين؛ سيتم تحليل الشيتات المتاحة.')
        parts = []
        for sheet_name, frame in sheets.items():
            if frame.empty:
                continue
            frame = frame.dropna(how='all').copy()
            frame['source_sheet'] = sheet_name
            parts.append(frame)
        if not parts:
            raise ValueError('جميع شيتات ملف 2024 فارغة.')
        st.info('تم دمج شيتات 2024: ' + '، '.join(f'{x["source_sheet"].iloc[0]} ({len(x)} سجل)' for x in parts))
        return pd.concat(parts, ignore_index=True, sort=False)
    return pd.read_excel(file, sheet_name=0)

def prepare(raw, mapping, year):
    normalized={norm(c):c for c in raw.columns}
    rename={}
    missing=[]
    for original, target in mapping.items():
        match=normalized.get(norm(original))
        if match is None: missing.append(original)
        else: rename[match]=target
    if missing: raise ValueError(f'ملف {year}: الأعمدة المطلوبة غير موجودة: {", ".join(missing)}. الأعمدة المتاحة: {", ".join(map(str,raw.columns))}')
    df=raw.rename(columns=rename)[list(mapping.values())].copy()
    df['year']=str(year)
    df['employee_id']=df['employee_id'].astype('string').str.strip().str.replace(r'\.0$', '', regex=True)
    df['employee_id']=df['employee_id'].replace({'':'', 'nan':pd.NA, '<NA>':pd.NA})
    for col in ['employee_name','entity']:
        df[col]=df[col].astype('string').str.strip().fillna('غير محدد').replace('', 'غير محدد')
    clean_days=df['days'].astype('string').str.replace('٫','.',regex=False).str.replace('٬','',regex=False).str.replace(',','',regex=False)
    for a,b in zip('٠١٢٣٤٥٦٧٨٩','0123456789'): clean_days=clean_days.str.replace(a,b,regex=False)
    df['days']=pd.to_numeric(clean_days, errors='coerce')
    df=df.dropna(how='all',subset=['employee_id','employee_name','days'])
    return df

def summarize(df):
    return {'السجلات':len(df), 'الأيام':df['days'].sum(), 'الموظفون':df['employee_id'].dropna().nunique(), 'المتوسط':df['days'].mean()}

def pct(old,new):
    if old==0: return 'غير قابلة للحساب (الأساس صفر)' if new else '0.0%'
    return f'{(new-old)/old*100:+.1f}%'

def group_compare(a,b,field):
    left=a.groupby(field,dropna=False).agg(سجلات_2024=('year','size'),أيام_2024=('days','sum'),موظفون_2024=('employee_id','nunique'))
    right=b.groupby(field,dropna=False).agg(سجلات_2025=('year','size'),أيام_2025=('days','sum'),موظفون_2025=('employee_id','nunique'))
    out=left.join(right,how='outer').fillna(0).reset_index()
    out['فرق_السجلات']=out['سجلات_2025']-out['سجلات_2024']
    out['فرق_الأيام']=out['أيام_2025']-out['أيام_2024']
    out['تغير_السجلات_%']=out.apply(lambda r: round((r['فرق_السجلات']/r['سجلات_2024'])*100,1) if r['سجلات_2024'] else None,axis=1)
    return out.sort_values('سجلات_2025',ascending=False)

c1,c2=st.columns(2)
with c1: f24=st.file_uploader(' ملف 2024 (Excel أو CSV)',type=['xlsx','xls','csv'],key='f24')
with c2: f25=st.file_uploader(' ملف 2025 (Excel أو CSV)',type=['xlsx','xls','csv'],key='f25')
if not (f24 and f25):
    st.info('')
    st.stop()
try:
    a=prepare(read_file(f24, 2024),FIELDS_2024,2024)
    b=prepare(read_file(f25, 2025),FIELDS_2025,2025)
except Exception as e:
    st.error(f'تعذرت قراءة الملفات: {e}')
    st.stop()

st.caption('تُجمع جميع السجلات بغض النظر عن نوع الإجازة، دون تصنيف أو فلترة حسب النوع.')
st.warning('تحققي من أن «مكان العمل» في 2024 يعادل «اسم الدائرة» في 2025 قبل اعتماد مقارنة الجهات.')
invalid_a=a['days'].isna().sum(); invalid_b=b['days'].isna().sum()
negative_a=(a['days']<0).sum();negative_b=(b['days']<0).sum()
if invalid_a or invalid_b or negative_a or negative_b:
    st.warning(f'فحص جودة البيانات: أيام غير رقمية/مفقودة 2024: {invalid_a}، 2025: {invalid_b} | أيام سالبة 2024: {negative_a}، 2025: {negative_b}. السجلات ذات الأيام غير الرقمية تدخل في عدد السجلات ولا تدخل في مجموع الأيام.')
if a.empty or b.empty: st.warning('لا توجد سجلات في إحدى السنتين ضمن الفلتر المحدد.')
s24=summarize(a);s25=summarize(b)
st.subheader('المؤشرات الرئيسية')
cols=st.columns(4)
for col,(key,title) in zip(cols,[('السجلات','عدد سجلات الإجازات'),('الأيام','إجمالي أيام الإجازة'),('الموظفون','الموظفون المميزون'),('المتوسط','متوسط الأيام للسجل')]):
    with col:
        st.metric(title, f'{s25[key]:,.1f}' if key in ('الأيام','المتوسط') else f'{s25[key]:,}',delta=pct(s24[key],s25[key]))
        st.caption(f'2024: {s24[key]:,.1f}' if key in ('الأيام','المتوسط') else f'2024: {s24[key]:,}')

st.subheader('مقارنة إجمالية')
summary=pd.DataFrame([{'السنة':'2024',**s24},{'السنة':'2025',**s25}])
st.dataframe(summary,use_container_width=True,hide_index=True)
chart_df=summary.melt(id_vars='السنة',value_vars=['السجلات','الأيام','الموظفون'],var_name='المؤشر',value_name='القيمة')
st.plotly_chart(px.bar(chart_df,x='السنة',y='القيمة',color='السنة',facet_col='المؤشر',text_auto='.0f',title='مقارنة المؤشرات بين السنتين'),use_container_width=True)

st.subheader('الجهات الحكومية')
entity=group_compare(a,b,'entity')
st.dataframe(entity.rename(columns={'entity':'الجهة'}),use_container_width=True,hide_index=True)
st.plotly_chart(px.bar(entity.head(15),x='entity',y=['سجلات_2024','سجلات_2025'],barmode='group',title='أعلى 15 جهة حسب عدد السجلات في 2025',labels={'entity':'الجهة','value':'السجلات','variable':'السنة'}),use_container_width=True)

st.subheader('مقارنة الموظفين')
ids24=set(a['employee_id'].dropna());ids25=set(b['employee_id'].dropna())
cc=st.columns(3)
cc[0].metric('ظهروا في السنتين',len(ids24&ids25))
cc[1].metric('ظهروا في 2025 فقط',len(ids25-ids24))
cc[2].metric('ظهروا في 2024 فقط',len(ids24-ids25))
st.caption('المقارنة هنا بحسب رقم الموظف، ولا تثبت أن الموظف لم يأخذ إجازة خارج نطاق الملفين.')

st.subheader(' النتائج')
for key,label in [('السجلات','عدد سجلات الإجازات'),('الأيام','إجمالي أيام الإجازة'),('الموظفون','عدد الموظفين'),('المتوسط','متوسط الأيام لكل سجل')]:
    diff=s25[key]-s24[key]
    verb='ارتفع' if diff>0 else ('انخفض' if diff<0 else 'لم يتغير')
    st.write(f'• {verb} {label} من {s24[key]:,.1f} في 2024 إلى {s25[key]:,.1f} في 2025 (التغير: {pct(s24[key],s25[key])}).')
st.info('هذه النتائج تصف الاختلاف بين الملفين فقط ولا تثبت سبب الزيادة أو الانخفاض. ولأن تواريخ الإجازات مستبعدة، لا يمكن التحقق من توزيع الأيام على الأشهر أو من تداخل الإجازات.')

st.subheader('تنزيل النتائج')
output=io.BytesIO()
with pd.ExcelWriter(output,engine='openpyxl') as writer:
    summary.to_excel(writer,sheet_name='الملخص',index=False)
    entity.to_excel(writer,sheet_name='مقارنة الجهات',index=False)
    a.to_excel(writer,sheet_name='بيانات 2024 الموحدة',index=False)
    b.to_excel(writer,sheet_name='بيانات 2025 الموحدة',index=False)
st.download_button(' تحميل تقرير المقارنة Excel',data=output.getvalue(),file_name='leave_comparison_2024_2025.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

