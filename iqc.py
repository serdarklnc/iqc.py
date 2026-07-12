import streamlit as st
import pandas as pd
import numpy as np
import os

# Sayfa Genişliği ve Mobil Uyumluluk Ayarı
st.set_page_config(page_title="Sabah QC Takip Paneli", layout="wide", initial_sidebar_state="expanded")

st.title("🔬 İç Kalite Kontrol Takip Paneli")
st.caption("Cihaz bazlı odaklanma ve anlık aksiyon takibi")

# --- 1. VERİ İŞLEME FONKSİYONU ---
def qc_verisi_hazirla(df, sd_siniri):
    benim_cihazlarim = ["INFINTY_c8000_0", "INFINTY_c8000_1", "INFINTY_c8000_2", "INFINTY_c8000_3", "INFINTY_c8000_4", "INFINTY_c8000_5", "INFINTY_c8000_6", "STANDALONE", "COBAS_E601_MRKZ", "COBAS_6000_Idrar"]
    benim_kontrol_adlarım = ["PCCC1", "PCCC2",  "PC TM1", "PC TM2", "PC U1", "PC U2", "PC THYRO1", "PC THYRO2", "PC AMH1", "PC AMH2", "PC CARD1", "PCCARD2", "PC G1", "PC G2", "PC V1", "PC V2", "PC VITDT1", "PC VITDT2", "TDMC1", "TDMC2", "TDMC3", "PC ISD1", "PC ISD2", "PC ISD3", "PC MM1", "PC MM2", "AMM-N", "AMM-P", "CYS-1", "CYS-2", "CYS-3", "ID PCCC1", "ID PCCC2", "PN PUC", "PP PUC", "PC PCCC1", "PC PCCC2", "PC A-CCP1", "PC A-CCP2", "B2MG1", "B2MG2", "ZNCRC01", "ZNCRC02"]
    
    # Filtreleme
    filtreli_df = df[df['Cihaz'].isin(benim_cihazlarim) & df['Kontrol Adı'].isin(benim_kontrol_adlarım)].copy()
    filtreli_df['Sonuç SD'] = pd.to_numeric(filtreli_df['Sonuç SD'], errors='coerce')
    
    # SD Sınırı
    hatali_kontroller = filtreli_df[filtreli_df['Sonuç SD'].abs() > sd_siniri].copy()
    if hatali_kontroller.empty:
        return pd.DataFrame()
        
    # Sizin tercih ettiğiniz Test ismine göre alfabetik sıralama
    sirali_liste = hatali_kontroller.sort_values(by='Test', ascending=True)
    
    # Sadeleştirme (Cihaz, Modül ve Test bazında teke düşürme)
    sadelestirilmis = sirali_liste.drop_duplicates(subset=['Cihaz', 'Test', 'Cihaz Modül No'], keep='first')
    
    # Son Sıralama (Modül ve Teste göre)
    final_sirali = sadelestirilmis.sort_values(by=['Cihaz', 'Test', 'Cihaz Modül No']).copy()
    return final_sirali[['Cihaz', 'Test', 'Cihaz Modül No', 'Sonuç SD']].reset_index(drop=True)


# --- 2. DOSYA BULMA VE SESSON_STATE HAFIZASI ---
varsayilan_dosya = "iqc_060726.xlsx"
df_raw = None

# Sol taraftaki Yan Menüye (Sidebar) Filtreleri Taşıyoruz
with st.sidebar:
    st.header("⚙️ Kontrol Paneli")
    sd_siniri = st.number_input("Hedef SD Sınırı Filtresi", min_value=0.0, max_value=5.0, value=1.5, step=0.1)
    st.markdown("---")
    
    # Klasörde dosya kontrolü
    if os.path.exists(varsayilan_dosya):
        st.success(f"🔄 '{varsayilan_dosya}' otomatik yüklendi.")
        if 'otomatik_veri' not in st.session_state:
            st.session_state.otomatik_veri = pd.read_excel(varsayilan_dosya)
        df_raw = st.session_state.otomatik_veri
    else:
        yuklenen_dosya = st.file_uploader("Excel dosyasını buraya yükleyin:", type=["xlsx"])
        if yuklenen_dosya is not None:
            df_raw = pd.read_excel(yuklenen_dosya)

# --- 3. ANA EKRAN MANTIĞI VE CİHAZ ODAKLI TASARIM ---
if df_raw is not None:
    # --- Tarih bilgisini hatasız yakalama alanı ---
    tarih_str = ""
    if 'Çalışma Tarihi' in df_raw.columns:
        gecerli_satirlar = df_raw['Çalışma Tarihi'].dropna()
        if not gecerli_satirlar.empty:
            ham_tarih = gecerli_satirlar.iloc[0]
            try:
                # Veri tipi ne olursa olsun GG.AA.YYYY formatına çeviriyoruz
                tarih_str = f" ({pd.to_datetime(ham_tarih, dayfirst=True).strftime('%d.%m.%Y')})"
            except:
                # Beklenmeyen bir metin formatı gelirse hata vermemesi için string halini basıyoruz
                tarih_str = f" ({str(ham_tarih)})"
    
    # Raporu kullanıcının seçtiği sınıra göre üret
    tum_rapor_df = qc_verisi_hazirla(df_raw, sd_siniri)

    if tum_rapor_df.empty:
        st.info(f"Harika! Seçili kriterlerde {sd_siniri} SD sınırını aşan hiçbir test bulunmadı.")
    else:
        # Hafızada aksiyonlar için yer aç
        if 'aksiyonlar' not in st.session_state:
            st.session_state.aksiyonlar = {}

        # İhlali olan benzersiz cihazları çekip Yan Menüye Seçim Kutusu koyuyoruz
        ihlalli_cihazlar = sorted(tum_rapor_df['Cihaz'].unique())
        
        with st.sidebar:
            st.subheader("📱 Cihaz Seçimi")
            secilen_cihaz = st.radio(
                "Başında olduğunuz cihazı seçin:", 
                ihlalli_cihazlar,
                help="Sadece seçtiğiniz cihaza ait modüller listelenir."
            )
        
        # Veriyi sadece seçilen cihaza göre filtrele
        cihaz_df = tum_rapor_df[tum_rapor_df['Cihaz'] == secilen_cihaz].copy()

        # Tarih bilgisi eklenmiş dinamik başlık alanı
        st.subheader(f"🤖 {secilen_cihaz} — İhlalli Modül ve Test Listesi{tarih_str}")
        st.info(f"Bu cihazda toplam **{len(cihaz_df)}** sorunlu kit/test kombinasyonu incelenmeyi bekliyor.")

        # Seçilen cihaza ait kartları ekrana basıyoruz
        for index, row in cihaz_df.iterrows():
            modul = row['Cihaz Modül No']
            test = row['Test']
            sd_degeri = row['Sonuç SD']
            
            unique_key = f"{secilen_cihaz}_{modul}_{test}_{index}"
            
            if unique_key not in st.session_state.aksiyonlar:
                st.session_state.aksiyonlar[unique_key] = {
                    "kalibrasyon": False, "maskeleme": False, "kontrol_tekrari": False, "not": ""
                }
            
            renk = "🔴" if sd_degeri > 0 else "🔵"
            kart_basligi = f"{renk} Modül: {modul} ➡️ Test: {test} | SD: {sd_degeri:+.2f}"
            
            ak = st.session_state.aksiyonlar[unique_key]
            if ak["kalibrasyon"] or ak["maskeleme"] or ak["kontrol_tekrari"]:
                kart_basligi += "  ✅ (İşlem Yapıldı)"

            with st.expander(kart_basligi):
                c1, c2, c3 = st.columns(3)
                with c1:
                    ak["kalibrasyon"] = st.checkbox("Kalibrasyon_OK", value=ak["kalibrasyon"], key=f"cal_{unique_key}")
                with c2:
                    ak["maskeleme"] = st.checkbox("Maskeli (Kapalı)", value=ak["maskeleme"], key=f"mask_{unique_key}")
                with c3:
                    ak["kontrol_tekrari"] = st.checkbox("Kontrol tekrarı_OK", value=ak["kontrol_tekrari"], key=f"kit_{unique_key}")
                
                ak["not"] = st.text_input("Açıklama / Durum Notu:", value=ak["not"], key=f"txt_{unique_key}")

        # --- 4. TÜM VERİLERİ DERLEYİP EXCEL DOSYASI YAPMA ---
        st.markdown("---")
        st.subheader("💾 Gün Sonu Kapanış")
        
        if st.button("Tüm Cihazların Değerlendirmesini Derle ve Excel Raporu Hazırla"):
            aksiyon_listesi = []
            
            for index, row in tum_rapor_df.iterrows():
                u_key = f"{row['Cihaz']}_{row['Cihaz Modül No']}_{row['Test']}_{index}"
                
                if u_key in st.session_state.aksiyonlar:
                    ak = st.session_state.aksiyonlar[u_key]
                    durumlar = []
                    if ak["kalibrasyon"]: durumlar.append("Kalibrasyon Yapıldı")
                    if ak["maskeleme"]: durumlar.append("Test Maskelendi")
                    if ak["kontrol_tekrari"]: durumlar.append("Kontrol Tekrarlandı")
                    
                    aksiyon_str = ", ".join(durumlar) if durumlar else "Aksiyon Alınmadı"
                    if ak["not"]:
                        aksiyon_str += f" (Not: {ak['not']})"
                else:
                    aksiyon_str = "Aksiyon Alınmadı"
                    
                aksiyon_listesi.append(aksiyon_str)
            
            çıktı_df = tum_rapor_df.copy()
            çıktı_df['Alınan Aksiyon ve Durum'] = aksiyon_listesi
            
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                çıktı_df.to_excel(writer, index=False, sheet_name='Sabah_Aksiyon_Raporu')
            
            st.download_button(
                label="📥 Tüm Listeyi Excel Olarak İndir",
                data=buffer.getvalue(),
                file_name="Rutin_Internal_QC_Aksiyon_Raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("Tüm cihazlardaki değerlendirmeleriniz tek bir dosyada birleştirildi!")
else:
    st.info("Lütfen çalışmak istediğiniz excel dosyasını uygulamanın bulunduğu klasöre yükleyin.")
