# Prompt 1 : nettoyage batch des segments Markdown
markdown_cleaning_prompt = """
You are a professional Markdown cleaning assistant. Your goal is to transform the provided markdown segment into a concise, readable, and well-structured plain text, keeping only the meaningful content. Do not add, remove, or invent content outside of the original text.

Requirements:
1. Remove all Markdown links, keeping only the link text.
2. Remove any HTML tags or embedded scripts.
3. Remove URLs, email addresses, or references to external websites.
4. Flatten lists into simple text without bullets or dashes.
5. Normalize whitespace: collapse multiple blank lines into a maximum of two.
6. Preserve headings as simple text but without Markdown symbols (#, ##, etc.).
7. Keep the text in the same language as the original content.

Output only the cleaned text of this segment with no additional data, text or comment.

Markdown segment: "{markdown_segment}"
"""

# Prompt 2 : génération du JSON final à partir du texte nettoyé
json_generation_prompt = """
You are a professional Markdown processing assistant. Your goal is to take the fully cleaned and concatenated text and generate a single JSON object for database insertion.

Requirements:
1. Generate the following fields in JSON exactly and in this order:
   - name → a title or slug of the article
   - description → a short summary of 2-3 sentences
   - link → the source URL
   - text_clean → the main cleaned content with a coherent title for the content at the top
2. Do not add any other fields or explanations.

Output ONLY the JSON object.

Cleaned text: "{cleaned_text}"
Source link: "{link}"
"""
