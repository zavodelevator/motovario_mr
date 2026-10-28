# Motovario electric motors: catalogue sources

Research date: 2026-10-27. Scope: IEC three-phase asynchronous motors, brake motors, single-phase, ATEX.

Note on access: the official motovario.com download pages were fetched and their document links were read. The `my.motovario.com` file endpoints and the directindustry copy were not retrievable from this session (allowlist or client error). Nothing was downloaded with curl or wget. Page counts and technical table contents could not be verified for the PDFs, because the PDF fetches returned binary data.

## 1. Candidate sources (best first)

1. **Motovario M Series electric motors download page (official)**
   - URL: https://www.motovario.com/eng/download/electric-motors--m-series
   - Language: English (page), with catalogues in several languages per the flag IDs
   - Contains: a list of 17 documents linking to the M-series technical catalogue, installation/use instructions, spare-parts table, EU Ecodesign datasheet (QL0363), EC 640/2009 application note, TECO-branded aluminium and cast-iron catalogues, and CAD configurator links. It is a landing page, not a PDF.
   - Direct PDF: no (links go through `my.motovario.com/file.php?s=...`; the EC 640/2009 item is a direct `download_file.php` PDF link)

2. **Technical catalogue, M / IEC size 56-132 (official, via the download page above)**
   - Reference: `my.motovario.com/file.php?s=42k9`, titled "TECHNICAL CATALOGUE - M / IEC Size 56-132"
   - Language: English (likely)
   - Contains: the main technical catalogue covering three-phase, brake, single-phase, double-polarity and high-starting-torque motors. This is the document most likely to carry the power, frame, pole, rpm, torque, current, efficiency and dimension tables. Not verified (the file was not retrievable).
   - Direct PDF: unclear. The `file.php` link was blocked from this session; the link type is not confirmed.

3. **TECHNICAL CATALOGUE STANDARD IEC ELECTRIC MOTORS, M, rev0 2023 (Motovario Poland mirror)**
   - URL: https://motovario.com.pl/wp-content/uploads/2023/12/TECHNICAL-CATALOGUE_M_IEC_STD_EN_rev0_2023.pdf
   - Language: English
   - Contains: a 2023 revision of the M IEC standard motor technical catalogue. Expected to contain the tables. Content was not readable; the fetch returned binary.
   - Direct PDF: yes (URL ends in `.pdf`, served from the Motovario Poland site). Size and page count not visible.

4. **M Series electric motors, product brochure (DP-M EN/2019/REV.0), mirrored via mmintercom**
   - URL: https://mmintercom.com/upload/publish/183/MOTOVARIO M-SERIES ELECTRIC MOTORS.pdf
   - Language: English
   - Contains: a short overview of TS/TH/TP and TBS/TBH/TBP motors. Power 0.09-90 kW, frame 63-280, poles 2/4/6, IP55 (IP54 for brake), insulation F, IEC 60034-30:2008. No numeric data tables. Use as an overview only.
   - Direct PDF: yes (third-party host, not an official Motovario site).

5. **MOTOVARIO TECHNICAL CATALOGUE, IEC STD (H, VAR) mirror, mmintercom**
   - URLs: https://mmintercom.com/upload/publish/190/MOTOVARIO TECHNICAL CATALOGUE_H_IEC_STD.pdf and https://mmintercom.com/upload/publish/193/MOTOVARIO TECHNICAL CATALOGUE_VAR_IEC_STD.pdf
   - These cover gear reducers and motovariators, not electric motors. Listed only to flag that they are not motor catalogues.

6. **Motovario "Electric motors M" datasheet mirror on motovarioprevodovky.cz (IE1/IE2)**
   - URL: https://www.motovarioprevodovky.cz/pdf/D_IE1_IE2_en.pdf
   - Language: English. Title on the search index: "TECHNICAL CATALOGUE STANDARD IEC ELECTRIC MOTORS". Its name suggests IE1/IE2 coverage, which is relevant to the IE2/IE3 question. Not verified; the file was not fetched.
   - Direct PDF: yes (URL ends in `.pdf`).

7. **Rossi TX Series catalogue (sister company, not Motovario)**
   - Landing page: https://www.rossi.com/en/Products/Electric-Motors/TX-Series
   - PDF: https://www.rossi.com/-/media/Feature/Download-Files/Technical-Catalogs/TX/TX-series-catalog-EN.pdf (19.16 MB per the page)
   - Covers: TX asynchronous three-phase standard and brake motors, IE3, IP55/IP66, IEC. The page does not mention Motovario. Use only if a TX-series catalogue is needed; it is not a Motovario document.

8. **Motovario EC Regulation 640/2009 application note (rev 3)**
   - URL: https://www.motovario.com/download_file.php?u=dXBsb2FkL2Rvd25sb2FkL2ZpbGUvZmlsZXMvMTUxMjE4MTcyNzJfcHRfMDFfYXBwbGljYXRpb25fb2ZfdGhlX2VjX3JlZ3VsYXRpb25fNjQwXzIwMDlfdG9fbW90b3ZhcmlvX2VsZWN0cmljX21vdG9yc19yZXZfM19lbi5wZGY%3D&f=pt_01_application_of_the_ec_regulation_640_2009_to_motovario_electric_motors_rev_3_en.pdf&e=1
   - Language: English. Direct PDF: yes. Covers efficiency-regulation applicability only, no motor data tables.

## 2. Best primary source

The **official M Series technical catalogue (IEC size 56-132)**, reached from https://www.motovario.com/eng/download/electric-motors--m-series, is the best primary source. It is the only electric-motor catalogue on Motovario's own site, it covers three-phase, brake, single-phase and high-starting-torque variants, and it is the document the download page links for technical data. The 2023 Poland M IEC PDF (candidate 3) is a useful direct-download fallback and appears to be the same family. Verify tables and page count before relying on either.

Gaps: no TX, TXF or ATEX electric-motor catalogue was found on motovario.com. TX belongs to Rossi. ATEX appears only on the worm-gear catalogue (VSF). The Teco-branded aluminium and cast-iron catalogues are listed on Motovario's page (AERV/AEQV and AESV/AESU series), but they are Teco products and are not Motovario-designed.

## 3. Public pricing

Motovario does not publish prices publicly. The download page and the catalogues contain no price lists, and the Rossi TX page shows "Contact us" rather than prices. Prices must be requested from Motovario or an authorised distributor.

## Sources

- [Motovario M Series electric motors, download page](https://www.motovario.com/eng/download/electric-motors--m-series)
- [Motovario download catalogues index](https://www.motovario.com/eng/download)
- [Motovario Poland, TECHNICAL CATALOGUE M IEC STD 2023 (PDF)](https://motovario.com.pl/wp-content/uploads/2023/12/TECHNICAL-CATALOGUE_M_IEC_STD_EN_rev0_2023.pdf)
- [Motovario M-series brochure, mirror (PDF)](https://mmintercom.com/upload/publish/183/MOTOVARIO M-SERIES ELECTRIC MOTORS.pdf)
- [Motovario IE1/IE2 IEC electric motors, mirror (PDF)](https://www.motovarioprevodovky.cz/pdf/D_IE1_IE2_en.pdf)
- [Motovario EC 640/2009 application note (PDF)](https://www.motovario.com/download_file.php?u=dXBsb2FkL2Rvd25sb2FkL2ZpbGUvZmlsZXMvMTUxMjE4MTcyNzJfcHRfMDFfYXBwbGljYXRpb25fb2ZfdGhlX2VjX3JlZ3VsYXRpb25fNjQwXzIwMDlfdG9fbW90b3ZhcmlvX2VsZWN0cmljX21vdG9yc19yZXZfM19lbi5wZGY%3D&f=pt_01_application_of_the_ec_regulation_640_2009_to_motovario_electric_motors_rev_3_en.pdf&e=1)
- [Rossi TX Series landing page (not Motovario)](https://www.rossi.com/en/Products/Electric-Motors/TX-Series)
- [Rossi TX series catalogue (PDF, not Motovario)](https://www.rossi.com/-/media/Feature/Download-Files/Technical-Catalogs/TX/TX-series-catalog-EN.pdf)
