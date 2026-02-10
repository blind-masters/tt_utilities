import polib
from deep_translator import GoogleTranslator
import time

def translate_po_file(input_file, output_file, source_lang, target_lang):
    # Initialize translator and read the .po file
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    po = polib.pofile(input_file)
    
    for entry in po:
        # Check if msgstr is empty (or None) and msgid has content
        if (entry.msgstr is None or entry.msgstr == "") and entry.msgid:
            try:
                # Translate msgid to the target language and assign it to msgstr
                translation = translator.translate(entry.msgid)
                entry.msgstr = translation
                print(f"Translated: '{entry.msgid}' to '{entry.msgstr}'")
                time.sleep(0.5)  # Delay to avoid API rate limits
            except Exception as e:
                print(f"Error translating '{entry.msgid}': {e}")
                
    # Ensure no msgstr is None before saving
    for entry in po:
        if entry.msgstr is None:
            entry.msgstr = ""

    # Save the updated .po file
    po.save(output_file)
    print(f"Translation complete! Saved to {output_file}")

# Usage example
input_po_file = 'messages.po'
output_po_file = 'translated_file.po'
source_language = 'en'
target_language = 'ar'

translate_po_file(input_po_file, output_po_file, source_language, target_language)