# Text parsing and cleaning helpers
import spacy
from spacy.matcher import PhraseMatcher
import re

text = """
John Doe is a backend engineer with 3 years of experience.
Skilled in Python, FastAPI, and Docker.
Worked at Shopee as a Software Engineer.
Graduated from NUS with a Computer Science degree.
"""
skills_list = ["Python", "FastAPI", "Docker", "Kubernetes"]
nlp = spacy.load("en_core_web_sm")
def parseResume(text):

    doc = nlp(text)

    print("1st process")
    for ent in doc.ents:
        print(ent.text, ent.label_)
        
    found_skills = []

    for token in doc:
        if token.text in skills_list:
            found_skills.append(token.text)
    print("2nd process")
    print(found_skills)

    matcher = PhraseMatcher(nlp.vocab)
    patterns = [nlp(skill) for skill in skills_list]

    matcher.add("SKILLS", patterns)


    matches = matcher(doc)


    
    extracted_skills = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        extracted_skills.add(span.text)

    print("3rd process")
    print(extracted_skills)
    
    return {
        "message": "Parse done"
    }
    
    

# very basic extraction logic
def extract_email(text: str):
    match = re.search(r"[\\w\\.-]+@[\\w\\.-]+", text)
    return match.group(0) if match else None

def extract_name(text: str):
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return None

def extract_skills(text: str):
    doc = nlp(text)
    matcher = PhraseMatcher(nlp.vocab)
    patterns = [nlp(skill) for skill in skills_list]

    matcher.add("SKILLS", patterns)

    matches = matcher(doc)

    extracted_skills = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        extracted_skills.add(span.text)

    return extracted_skills

