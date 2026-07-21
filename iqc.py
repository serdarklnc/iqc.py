import streamlit as st
import pandas as pd
import numpy as np
import os

# Sayfa Genişliği ve Mobil Uyumluluk Ayarı
st.set_page_config(page_title="Sabah QC Takip Paneli", layout="wide", initial_sidebar_state="expanded")

st.title("🔬 İç Kalite Kontrol Takip Paneli")
st.caption("Cihaz bazlı odaklanma ve anlık aksiyon takibi")

# --- 1. AKILLI VE SEVİYE DUYARLI VERİ İŞLEME FONKSİYONU ---
def qc_verisi_hazirla(df, sd_siniri):
    benim_cihazlarim = ["INFINTY_c8000_0", "INFINTY_c8000_1", "INFINTY_c8000_2", "INFINTY_c8000_3", "INFINTY_c8000_4", "INFINTY_c8000_5", "INFINTY_c8000_6", "STANDALONE", "COBAS_E601_MRKZ", "COBAS_6000_Idrar"]
    benim_kontrol_adlarım = ["PCCC1", "PCCC2",  "PC TM1", "PC TM2", "PC U1", "PC U2", "PC THYRO1", "PC THYRO2", "PC AMH1", "PC AMH2", "PC CARD1", "PCCARD2", "PC G1", "PC G2", "PC V1", "PC V2", "PC VITDT1", "PC VITDT2", "TDMC1", "TDMC2", "TDMC3", "PC ISD1", "PC ISD2", "PC ISD3", "PC MM1", "PC MM2", "AMM-N", "AMM-P", "CYS-1", "CYS-2", "CYS-3", "ID PCCC1", "ID PCCC2", "PN PUC", "PP PUC", "PC PCCC1", "PC PCCC2", "PC A-CCP1", "PC A-CCP2", "B2MG1", "B2MG2", "ZNCRC01", "ZNCRC02"]
    
    # Filtreleme
    filtreli_df = df[df['Cihaz'].isin(benim_cihazlarim) & df['Kontrol Adı'].isin(benim_kontrol_adlarım)].copy()
    filtreli_df['Sonuç SD'] = pd.to_numeric(filtreli_df['Sonuç SD'], errors='coerce')
    
    # Kronolojik sıralama (Zaman damgasına göre)
    if 'Çalışma Tarihi' in filtreli_df.columns:
        try:
            filtreli_df['Gecici_Zaman'] = pd.to_datetime(filtreli_df['Çalışma Tarihi'], dayfirst=True)
            filtreli_df = filtreli_df.sort_values(by=['Cihaz', 'Cihaz Modül No', 'Test', 'Kontrol Adı', 'Gecici_Zaman'])
        except:
            pass

    analiz_listesi = []
    
    # Testleri 'Cihaz', 'Cihaz Modül No' ve 'Test' düzeyinde grupluyoruz
    test_gruplari = filtreli_df.groupby(['Cihaz', 'Cihaz Modül No', 'Test'])
    
    for (cihaz, modul, test), test_grup in test_gruplari:
        seviyeler = test_grup['Kontrol Adı'].unique()
        
        seviye_analizleri = {}
        toplam_ihlalli_seviye_sayisi = 0
        cozulen_seviye_sayisi = 0
        
        for seviye in seviyeler:
            seviye_grup = test_grup[test_grup['Kontrol Adı'] == seviye]
            calismalar = seviye_grup.to_dict('records')
            
            ihlalli_calisma = None
            basarili_tekrar = None
            
            for calisma in calismalar:
                sd_val = calisma['Sonuç SD']
                if pd.isna(sd_val):
                    continue
                
                if ihlalli_calisma is None and abs(sd_val) > sd_siniri:
                    ihlalli_calisma = calisma
                elif ihlalli_calisma is not None and abs(sd_val) <= sd_siniri:
                    basarili_tekrar = calisma
            
            if ihlalli_calisma is not None:
                toplam_ihlalli_seviye_sayisi += 1
                if basarili_tekrar is not None:
                    cozulen_seviye_sayisi += 1
                    seviye_analizleri[seviye] = {
                        'Ihlal_SD': ihlalli_calisma['Sonuç SD'],
                        'Tekrar_SD': basarili_tekrar['Sonuç SD'],
                        'Durum': 'Cozuldu'
                    }
                else:
                    seviye_analizleri[seviye] = {
                        'Ihlal_SD': ihlalli_calisma['Sonuç SD'],
                        'Tekrar_SD': None,
                        'Durum': 'Sorunlu'
                    }

        if toplam_ihlalli_seviye_sayisi == 0:
            continue
            
        if toplam_ihlalli_seviye_sayisi == cozulen_seviye_sayisi:
            durum = 'Otomatik_OK'
        else:
            durum = 'Sorunlu'
            
        sd_detay_listesi = []
        for sev, veri in seviye_analizleri.items():
            if veri['Durum'] == 'Cozuldu':
                sd_detay_listesi.append(f"{sev}: {veri['Ihlal_SD']:+.2f}➡️({veri['Tekrar_SD']:+.2f})")
            else:
                sd_detay_listesi.append(f"{sev}: {veri['Ihlal_SD']:+.2f}")
                
        final_sd_metni = " | ".join(sd_detay_listesi)
        
        analiz_listesi.append({
            'Cihaz': cihaz,
            'Cihaz Modül No': modul,
            'Test': test,
            'Sonuç SD': final_sd_metni,
            'Durum': durum
        })

    final_df = pd.DataFrame(analiz_listesi)
    if final_df.empty:
        return pd.DataFrame()
        
    final_df = final_df.sort_values(by=['Cihaz', 'Test', 'Cihaz Modül No']).reset_index(drop=True)
    return final_df


# --- 2. DOSYA BULMA VE SESSION_STATE HAFIZASI ---
varsayilan_dosya = "iqc_060726.xlsx"
df_raw = None

def temiz_excel_oku(dosya_objesi):
    df_raw = pd.read_excel(dosya_objesi, header=None)
    
    header_idx = None
    for idx, row in df_raw.iterrows():
        if any(isinstance(val, str) and "Cihaz" in val for val in row.values):
            header_idx = idx
            break
            
    if header_idx is None:
        raise ValueError("Excel dosyasında 'Cihaz' sütunu bulunamadı. Lütfen doğru dosyayı yüklediğinizden emin olun.")
        
    columns = df_raw.iloc[header_idx].tolist()
    columns = [col.strip() if isinstance(col, str) else col for col in columns]
    
    df_data = df_raw.iloc[header_idx + 1:].copy()
    df_data.columns = columns
    
    df_data = df_data.dropna(subset=['Cihaz'])
    df_data = df_data.reset_index(drop=True)
    
    return df_data


with st.sidebar:
    st.header("⚙️ Kontrol Paneli")
    sd_siniri = st.number_input("Hedef SD Sınırı Filtresi", min_value=0.0, max_value=5.0, value=1.5, step=0.1)
    
    # YENİ FİLTRE: Sadece müdahale bekleyen aktif sorunlu testleri göster
    sadece_bekleyenler = st.toggle("🔍 Sadece Müdahale Bekleyenleri Göster", value=False, help="Çözülmüş veya onaylanmış testleri ekrandan gizler.")
    st.markdown("---")
    
    if os.path.exists(varsayilan_dosya):
        st.success(f"🔄 '{varsayilan_dosya}' otomatik yüklendi.")
        if 'otomatik_veri' not in st.session_state:
            st.session_state.otomatik_veri = temiz_excel_oku(varsayilan_dosya)
        df_raw = st.session_state.otomatik_veri
    else:
        yuklenen_dosya = st.file_uploader("Excel dosyasını buraya yükleyin:", type=["xlsx"])
        if yuklenen_dosya is not None:
            df_raw = temiz_excel_oku(yuklenen_dosya)

# --- 3. ANA EKRAN MANTIĞI VE CİHAZ ODAKLI TASARIM ---
if df_raw is not None:
    tarih_str = ""
    if 'Çalışma Tarihi' in df_raw.columns:
        gecerli_satirlar = df_raw['Çalışma Tarihi'].dropna()
        if not gecerli_satirlar.empty:
            ham_tarih = gecerli_satirlar.iloc[0]
            try:
                tarih_str = f" ({pd.to_datetime(ham_tarih, dayfirst=True).strftime('%d.%m.%Y')})"
            except:
                tarih_str = f" ({str(ham_tarih)})"
    
    tum_rapor_df = qc_verisi_hazirla(df_raw, sd_siniri)

    if tum_rapor_df.empty:
        st.info(f"Harika! Seçili kriterlerde {sd_siniri} SD sınırını aşan hiçbir test bulunmadı.")
    else:
        if 'aksiyonlar' not in st.session_state:
            st.session_state.aksiyonlar = {}

        ihlalli_cihazlar = sorted(tum_rapor_df['Cihaz'].unique())
        
        with st.sidebar:
            st.subheader("📱 Cihaz Seçimi")
            secilen_cihaz = st.radio(
                "Başında olduğunuz cihazı seçin:", 
                ihlalli_cihazlar,
                key="device_radio"
            )
        
        cihaz_df = tum_rapor_df[tum_rapor_df['Cihaz'] == secilen_cihaz].copy()

        st.subheader(f"🤖 {secilen_cihaz} — İhlalli Modül ve Test Listesi{tarih_str}")
        
        toplam_is = len(cihaz_df)
        otomatik_cozulen = len(cihaz_df[cihaz_df['Durum'] == 'Otomatik_OK'])
        aktif_bekleyen = toplam_is - otomatik_cozulen
        st.info(f"Bu cihazda toplam **{toplam_is}** ihlalli durum var. (🚨 **{aktif_bekleyen}** Müdahale Bekleyen | 🟢 **{otomatik_cozulen}** Kendiliğinden Çözülmüş)")

        # Seçilen cihaza ait kartları ekrana basıyoruz
        for index, row in cihaz_df.iterrows():
            modul = row['Cihaz Modül No']
            test = row['Test']
            sd_yazisi = row['Sonuç SD']
            durum = row['Durum']
            
            unique_key = f"{secilen_cihaz}_{modul}_{test}_{index}"
            
            # Aksiyon durumları hafızası
            if unique_key not in st.session_state.aksiyonlar:
                st.session_state.aksiyonlar[unique_key] = {
                    "kalib_kontrol_ok": True if durum == 'Otomatik_OK' else False, 
                    "maskeleme": False, 
                    "karar_devam": False, 
                    "not": "Sistem tarafından tespit edilen başarılı seviye tekrarı." if durum == 'Otomatik_OK' else ""
                }
            
            ak = st.session_state.aksiyonlar[unique_key]

            # DİNAMİK RENK VE DURUM TESPİTİ
            if durum == 'Otomatik_OK':
                renk = "🟢"
                durum_etiketi = " ✅ (Tekrarı OK)"
                islem_tamam = True
            elif ak["kalib_kontrol_ok"]:
                renk = "🟢"
                durum_etiketi = " ✅ (Kalibrasyon/Kontrol OK)"
                islem_tamam = True
            elif ak["karar_devam"]:
                renk = "🟡" # Sarı / Zümrüt dönüşüm
                durum_etiketi = " 🟡 (Karar: Devam)"
                islem_tamam = True
            elif ak["maskeleme"]:
                renk = "🔴" if "-" not in sd_yazisi else "🔵"
                durum_etiketi = " ⛔ (Maskelendi)"
                islem_tamam = True
            else:
                renk = "🔵" if "-" in sd_yazisi else "🔴"
                durum_etiketi = ""
                islem_tamam = False

            # FİLTRELEME: Eğer "Sadece Müdahale Bekleyenleri Göster" açık ve işlem tamamlanmışsa kartı atla
            if sadece_bekleyenler and islem_tamam:
                continue

            kart_basligi = f"{renk} Modül: {modul} ➡️ Test: {test} | SD: {sd_yazisi}{durum_etiketi}"

            with st.expander(kart_basligi):
                c1, c2, c3 = st.columns(3)
                with c1:
                    ak["kalib_kontrol_ok"] = st.checkbox("Kalibrasyon/Kontrol OK", value=ak["kalib_kontrol_ok"], key=f"cal_cnt_{unique_key}")
                with c2:
                    ak["maskeleme"] = st.checkbox("Maskeli (Kapalı)", value=ak["maskeleme"], key=f"mask_{unique_key}")
                with c3:
                    ak["karar_devam"] = st.checkbox("Karar: Devam", value=ak["karar_devam"], key=f"devam_{unique_key}")
                
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
                    if ak["kalib_kontrol_ok"]: durumlar.append("Kalibrasyon/Kontrol OK")
                    if ak["karar_devam"]: durumlar.append("Karar: Devam (Çalışmaya Verildi)")
                    if ak["maskeleme"]: durumlar.append("Test Maskelendi")
                    
                    aksiyon_str = ", ".join(durumlar) if durumlar else "Aksiyon Alınmadı"
                    if ak["not"]:
                        aksiyon_str += f" (Not: {ak['not']})"
                else:
                    aksiyon_str = "Aksiyon Alınmadı"
                    
                aksiyon_listesi.append(aksiyon_str)
            
            çıktı_df = tum_rapor_df.copy()
            çıktı_df['Alınan Aksiyon ve Durum'] = aksiyon_listesi
            
            if 'Durum' in çıktı_df.columns:
                çıktı_df = çıktı_df.drop(columns=['Durum'])
            
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                çıktı_df.to_excel(writer, index=False, sheet_name='Sabah_Aksiyon_Raporu')
            
            # Dinamik dosya adı belirleme
            tarih_eki = tarih_str.replace("(", "").replace(")", "").strip() if tarih_str else "Rutin"
            dosya_adi = f"QC_Aksiyon_Raporu_{tarih_eki}.xlsx"
            
            st.download_button(
                label="📥 Tüm Listeyi Excel Olarak İndir",
                data=buffer.getvalue(),
                file_name=dosya_adi,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("Tüm cihazlardaki değerlendirmeleriniz tek bir dosyada birleştirildi!")
else:
    st.info("Lütfen çalışmak istediğiniz excel dosyasını uygulamanın bulunduğu klasöre yükleyin.")
