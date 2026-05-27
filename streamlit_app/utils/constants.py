"""Shared constants for the Streamlit dashboard."""

# Brazilian state name mapping
STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapa",
    "BA": "Bahia", "CE": "Ceara", "DF": "Distrito Federal", "ES": "Espirito Santo",
    "GO": "Goias", "MA": "Maranhao", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso", "PA": "Para", "PB": "Paraiba", "PE": "Pernambuco",
    "PI": "Piaui", "PR": "Parana", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RO": "Rondonia", "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina",
    "SE": "Sergipe", "SP": "Sao Paulo", "TO": "Tocantins",
}

REGION_MAP = {
    "SP": "Southeast", "RJ": "Southeast", "MG": "Southeast", "ES": "Southeast",
    "PR": "South",     "SC": "South",     "RS": "South",
    "BA": "Northeast", "CE": "Northeast", "PE": "Northeast", "MA": "Northeast",
    "PB": "Northeast", "RN": "Northeast", "AL": "Northeast", "SE": "Northeast",
    "PI": "Northeast",
    "GO": "Central-West", "MT": "Central-West", "MS": "Central-West", "DF": "Central-West",
    "AM": "North", "PA": "North", "RO": "North", "AC": "North",
    "AP": "North", "RR": "North", "TO": "North",
}

PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]

# Plotly color palette
PALETTE = {
    "primary":   "#1f77b4",
    "secondary": "#ff7f0e",
    "success":   "#2ca02c",
    "danger":    "#d62728",
    "accent":    "#9467bd",
    "neutral":   "#7f7f7f",
}

REGION_COLORS = {
    "Southeast":    "#1f77b4",
    "South":        "#2ca02c",
    "Northeast":    "#ff7f0e",
    "Central-West": "#9467bd",
    "North":        "#d62728",
}
