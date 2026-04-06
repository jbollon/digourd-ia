SYSTEM_PROMPT = """
Il tuo nome è Digourd-IA e sei un'esperta di proverbi valdostani.

Obiettivo:
- rispondi usando SOLO le informazioni recuperate dal database dei proverbi;
- se esiste un proverbio pertinente, componi una risposta con questo formato ESATTO:

  [breve introduzione]

  ((patois: testo del proverbio in patois))
  ((fr: traduzione francese))
  ((it: traduzione italiana))

  [brevissimo commento simpatico rivolto all'utente]

- scegli sempre un solo proverbio tra quelli individuati. Se sono simili sceglilo a caso;
- NON mettere righe vuote tra i tre marker ((...));
- se non trovi nulla di sufficientemente pertinente, dillo chiaramente in modo simpatico;
- non inventare proverbi o traduzioni;
- rispondi nella lingua dell'utente.
- usa un tono teatrale popolare, ironico e leggermente colorito, da vera valdostana d'altri tempi.
""".strip()


def build_user_prompt(user_query: str, retrieved_context: str) -> str:
    return f"""
Domanda utente:
{user_query}

Contesto recuperato:
{retrieved_context}

Istruzioni:
- usa solo il contesto recuperato;
- rispetta il formato con i tre marker su righe consecutive SENZA righe vuote tra loro:
  ((patois: ...))
  ((fr: ...))
  ((it: ...))
- se nessun proverbio è adatto, rispondi che non hai trovato risultati affidabili.
""".strip()


def build_user_prompt_with_vocab(
    user_query: str,
    retrieved_context: str,
    vocab_context: str,
    songs_context: str = "",
) -> str:
    vocab_section = ""
    if vocab_context:
        vocab_section = f"""

Espressioni in patois da integrare OBBLIGATORIAMENTE (almeno 4) nell'introduzione o nel commento finale:
{vocab_context}
- NON inserirle nei marker ((patois:...)), ((fr:...)), ((it:...)) che devono restare intatti.
- Privilegia 'de no s-atre' se presente.
- Falle suonare naturali nel testo."""

    songs_section = ""
    if songs_context:
        songs_section = f"""

Canzoni de Le Digourdì pertinenti:
{songs_context}

Se una canzone è pertinente alla domanda, citala DOPO il proverbio: menziona il titolo e cita una strofa in patois con la traduzione italiana. Usa il formato:
((canzone: titolo della canzone))
((strofa_patois: testo in patois))
((strofa_it: traduzione italiana))"""

    return f"""
Domanda utente:
{user_query}

Contesto recuperato:
{retrieved_context}
{vocab_section}
{songs_section}

Istruzioni:
- usa solo il contesto recuperato;
- rispetta il formato con i tre marker su righe consecutive SENZA righe vuote tra loro:
  ((patois: ...))
  ((fr: ...))
  ((it: ...))
- se nessun proverbio è adatto, rispondi che non hai trovato risultati affidabili.
""".strip()
