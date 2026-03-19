# devis/pdf.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, Image
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
import os

MOIS_FR = {
    1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
    5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
    9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
}

def date_fr(d):
    return f"{d.day:02d} {MOIS_FR[d.month]} {d.year}"

BLEU       = colors.HexColor('#1e3a5f')
BLEU_CLAIR = colors.HexColor('#2d6a9f')
GRIS_CLAIR = colors.HexColor('#f2f2f2')
GRIS       = colors.HexColor('#6c757d')
BLANC      = colors.white
NOIR       = colors.black


def montant_en_lettres(montant, devise='FCFA'):
    units = ['', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept',
             'huit', 'neuf', 'dix', 'onze', 'douze', 'treize', 'quatorze',
             'quinze', 'seize', 'dix-sept', 'dix-huit', 'dix-neuf']
    tens  = ['', 'dix', 'vingt', 'trente', 'quarante', 'cinquante',
             'soixante', 'soixante', 'quatre-vingt', 'quatre-vingt']

    def moins_de_mille(n):
        if n == 0: return ''
        elif n < 20: return units[n]
        elif n < 100:
            t, u = divmod(n, 10)
            if t == 7: return 'soixante-' + units[10 + u]
            elif t == 9: return 'quatre-vingt-' + units[u] if u else 'quatre-vingt'
            elif t == 8: return 'quatre-vingt-' + units[u] if u else 'quatre-vingts'
            else: return tens[t] + ('-' + units[u] if u else '')
        else:
            c, reste = divmod(n, 100)
            cent = ('cent' if c == 1 else units[c] + ' cent')
            cent += 's' if reste == 0 and c > 1 else ''
            return (cent + ' ' + moins_de_mille(reste)).strip()

    try:
        n = int(montant)
        if n == 0: return 'Zéro'
        resultat = ''
        if n >= 1000000:
            m, reste = divmod(n, 1000000)
            resultat += moins_de_mille(m) + ' million' + ('s' if m > 1 else '')
            n = reste
        if n >= 1000:
            m, reste = divmod(n, 1000)
            resultat += (' mille' if m == 1 else ' ' + moins_de_mille(m) + ' mille')
            n = reste
        if n > 0: resultat += ' ' + moins_de_mille(n)
        return resultat.strip().capitalize()
    except Exception:
        return str(montant)


def generer_pdf_devis(devis):
    """Génère un PDF pour un devis"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.8*cm, leftMargin=1.8*cm,
        topMargin=1.5*cm,   bottomMargin=1.5*cm
    )

    elements = []
    s_normal = ParagraphStyle('s_normal', fontSize=9, fontName='Helvetica', leading=13)
    s_bold   = ParagraphStyle('s_bold',   fontSize=9, fontName='Helvetica-Bold', leading=13)
    s_small  = ParagraphStyle('s_small',  fontSize=8, fontName='Helvetica', textColor=GRIS, leading=11)
    s_right  = ParagraphStyle('s_right',  fontSize=9, fontName='Helvetica', alignment=TA_RIGHT, leading=13)
    s_center = ParagraphStyle('s_center', fontSize=9, fontName='Helvetica', alignment=TA_CENTER)

    utilisateur  = devis.utilisateur
    client       = devis.client
    nom_emetteur = f"{utilisateur.first_name} {utilisateur.last_name}".strip() or utilisateur.username
    nom_client   = f"{client.nom} {client.prenom}".strip()

    # Devise du client (priorité) sinon FCFA
    devise = 'FCFA'
    if hasattr(client, 'pays_obj') and client.pays_obj:
        devise = client.pays_obj.symbole_devise

    # Infos taxe
    type_taxe_label = devis.type_taxe or 'TVA'
    taux_taxe_val   = devis.taux_taxe or (
        devis.lignes.first().tva if devis.lignes.exists() else 0
    )
    pays_label = devis.pays or ''

    # Adresse client
    adresse_client_lines = []
    if client.adresse:     adresse_client_lines.append(client.adresse)
    if client.ville:
        ville_str = client.ville
        if client.code_postal: ville_str += f" {client.code_postal}"
        if client.province:    ville_str += f" ({client.province})"
        adresse_client_lines.append(ville_str)
    if hasattr(client, 'pays_obj') and client.pays_obj:
        adresse_client_lines.append(client.pays_obj.nom)

    # Statut devis
    statut_map = {
        'en_attente': 'EN ATTENTE',
        'accepte': 'ACCEPTÉ',
        'refuse': 'REFUSÉ'
    }
    statut_texte = statut_map.get(devis.statut, '')

    # ══════════════════════════════════════════
    # EN-TÊTE
    # ══════════════════════════════════════════

    col_emetteur = [
        Paragraph(f"<b>{nom_emetteur}</b>", s_bold),
        Paragraph(utilisateur.email or '', s_normal),
    ]

    # ✅ AMÉLIORATION 1 : Logo client (optionnel)
    logo_element = None
    if hasattr(client, 'logo') and client.logo and hasattr(client.logo, 'path') and os.path.exists(client.logo.path):
        try:
            logo_element = Image(client.logo.path, width=3*cm, height=2*cm,
                                  kind='proportional')
        except Exception:
            logo_element = None

    col_titre = [
        Paragraph('DEVIS', ParagraphStyle(
            'titre', fontSize=22, fontName='Helvetica-Bold',
            textColor=BLEU, alignment=TA_CENTER
        )),
        Spacer(1, 0.7*cm),
        Paragraph(f"N° : <b>{devis.numero}</b>", ParagraphStyle(
            'num', fontSize=10, fontName='Helvetica', alignment=TA_CENTER
        )),
        Spacer(1, 0.2*cm),
        Paragraph(f"Date : {date_fr(devis.date_creation)}", ParagraphStyle(
            'date', fontSize=9, fontName='Helvetica',
            alignment=TA_CENTER, textColor=GRIS
        )),
        Spacer(1, 0.2*cm),
        Paragraph(f"Valable jusqu'au : {date_fr(devis.date_validite)}", ParagraphStyle(
            'validite', fontSize=9, fontName='Helvetica-Bold',
            alignment=TA_CENTER, textColor=BLEU
        )),
    ]

    col_client_content = [
        Paragraph("Proposé à :", s_small),
        Paragraph(f"<b>{nom_client}</b>", s_bold),
    ]
    if client.entreprise:
        col_client_content.append(Paragraph(client.entreprise, s_normal))
    if client.email:
        col_client_content.append(Paragraph(client.email, s_normal))
    
    # ✅ AMÉLIORATION 2 : Téléphone client
    if hasattr(client, 'telephone') and client.telephone:
        col_client_content.append(Paragraph(f"Tél: {client.telephone}", s_normal))
    elif hasattr(client, 'telephone_complet') and client.telephone_complet:
        col_client_content.append(Paragraph(client.telephone_complet, s_normal))
    
    for line in adresse_client_lines:
        col_client_content.append(Paragraph(line, s_small))
    
    # ✅ AMÉLIORATION 1 (suite) : Ajout du logo à la fin
    if logo_element:
        col_client_content.append(Spacer(1, 0.3*cm))
        col_client_content.append(logo_element)

    header_data  = [[col_emetteur, col_titre, col_client_content]]
    header_table = Table(header_data, colWidths=[6*cm, 6*cm, 6*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*cm))
    elements.append(HRFlowable(width="100%", thickness=2, color=BLEU))
    elements.append(Spacer(1, 0.3*cm))

    # ══════════════════════════════════════════
    # INFOS DEVIS
    # ══════════════════════════════════════════
    pays_str = f" — {pays_label}" if pays_label else ""
    infos_data = [[
        Paragraph(f"<b>Devis N° :</b> {devis.numero}", s_normal),
        Paragraph(f"<b>Date :</b> {date_fr(devis.date_creation)}", s_normal),
        Paragraph(
            f"<b>Valable jusqu'au :</b> {date_fr(devis.date_validite)}"
            f"{(' — <b>' + statut_texte + '</b>') if statut_texte else ''}"
            f"{pays_str}",
            s_normal
        ),
    ]]
    infos_table = Table(infos_data, colWidths=[6*cm, 6*cm, 6*cm])
    infos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRIS_CLAIR),
        ('PADDING',    (0, 0), (-1, -1), 8),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(infos_table)

    # Bandeau taxe + devise
    elements.append(Spacer(1, 0.2*cm))
    taxe_data = [[
        Paragraph(f"<b>Pays :</b> {pays_label or 'Non spécifié'}", s_normal),
        Paragraph(f"<b>Type de taxe :</b> {type_taxe_label}", s_normal),
        Paragraph(f"<b>Taux :</b> {taux_taxe_val}% — <b>Devise :</b> {devise}", s_bold),
    ]]
    taxe_table = Table(taxe_data, colWidths=[6*cm, 6*cm, 6*cm])
    taxe_table.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, -1), colors.HexColor('#e8f0fe')),
        ('PADDING',     (0, 0), (-1, -1), 8),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBEFORE',  (0, 0), (0, -1), 3, BLEU_CLAIR),
    ]))
    elements.append(taxe_table)
    elements.append(Spacer(1, 0.4*cm))

    # ══════════════════════════════════════════
    # TABLEAU DES LIGNES
    # ══════════════════════════════════════════
    lignes = devis.lignes.all()

    def th(txt):
        return Paragraph(f'<b>{txt}</b>', ParagraphStyle(
            'th', fontSize=9, fontName='Helvetica-Bold',
            textColor=BLANC, alignment=TA_CENTER
        ))

    entete = [th('Produit / Service'), th('Description'), th('Qté'),
              th(f'P.U. ({devise})'), th(f'{type_taxe_label} %'), th(f'HT ({devise})')]
    rows = [entete]

    for ligne in lignes:
        montant_ht = ligne.quantite * ligne.prix_unitaire
        rows.append([
            Paragraph(ligne.description, s_normal),
            Paragraph(ligne.description, s_small),
            Paragraph(str(ligne.quantite).rstrip('0').rstrip('.'), s_center),
            Paragraph(f"{ligne.prix_unitaire:,.2f}", s_right),
            Paragraph(f"{ligne.tva}%", s_center),
            Paragraph(f"{montant_ht:,.2f}", s_right),
        ])

    col_widths  = [4.5*cm, 4.5*cm, 1.5*cm, 2.5*cm, 2*cm, 3*cm]
    lignes_table = Table(rows, colWidths=col_widths)
    lignes_table.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), BLEU),
        ('TEXTCOLOR',    (0, 0), (-1, 0), BLANC),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0), 9),
        ('ALIGN',        (0, 0), (-1, 0), 'CENTER'),
        ('PADDING',      (0, 0), (-1, 0), 8),
        ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',     (0, 1), (-1, -1), 9),
        ('PADDING',      (0, 1), (-1, -1), 7),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BLANC, GRIS_CLAIR]),
        ('GRID',         (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(lignes_table)
    elements.append(Spacer(1, 0.4*cm))

    # ══════════════════════════════════════════
    # TOTAUX
    # ══════════════════════════════════════════
    total_ht  = devis.calculer_total_ht()
    total_tva = devis.calculer_tva()
    total_ttc = devis.calculer_total_ttc()

    totaux_data = [
        ['', '', Paragraph(f'<b>Sous total HT :</b>', s_right),
                 Paragraph(f"{total_ht:,.2f} {devise}", s_right)],
        ['', '', Paragraph(f'<b>{type_taxe_label} ({taux_taxe_val}%) :</b>', s_right),
                 Paragraph(f"{total_tva:,.2f} {devise}", s_right)],
        ['', '', Paragraph('<b>Total TTC :</b>', ParagraphStyle(
                    'tot', fontSize=10, fontName='Helvetica-Bold',
                    alignment=TA_RIGHT, textColor=BLEU)),
                 Paragraph(f"<b>{total_ttc:,.0f} {devise}</b>", ParagraphStyle(
                    'tot2', fontSize=10, fontName='Helvetica-Bold',
                    alignment=TA_RIGHT, textColor=BLEU))],
    ]
    totaux_table = Table(totaux_data, colWidths=[3*cm, 5*cm, 5.5*cm, 4.5*cm])
    totaux_table.setStyle(TableStyle([
        ('PADDING',   (0, 0), (-1, -1), 5),
        ('LINEABOVE', (2, 2), (3, 2), 1, BLEU),
        ('BACKGROUND',(2, 2), (3, 2), GRIS_CLAIR),
    ]))
    elements.append(totaux_table)

    # ══════════════════════════════════════════
    # MONTANT EN LETTRES
    # ══════════════════════════════════════════
    elements.append(Spacer(1, 0.3*cm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GRIS))
    elements.append(Spacer(1, 0.2*cm))
    lettres = montant_en_lettres(total_ttc, devise)
    elements.append(Paragraph(
        f"Arrêté le présent devis à la somme de "
        f"<b>{lettres} ({total_ttc:,.0f}) {devise}</b>.",
        ParagraphStyle('lettres', fontSize=9, fontName='Helvetica',
                       textColor=BLEU, leading=14)
    ))

    if devis.notes:
        elements.append(Spacer(1, 0.4*cm))
        elements.append(Paragraph(f"<b>Notes :</b> {devis.notes}", s_normal))

    # ══════════════════════════════════════════
    # PIED DE PAGE
    # ══════════════════════════════════════════
    elements.append(Spacer(1, 1*cm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GRIS))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph(
        f"Document généré automatiquement — {devis.numero} — {date_fr(devis.date_creation)}",
        ParagraphStyle('footer', fontSize=7, fontName='Helvetica',
                       textColor=GRIS, alignment=TA_CENTER)
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer