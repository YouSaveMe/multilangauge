from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
import openai
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영 환경에서는 특정 오리진만 허용하도록 수정해야 합니다.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase 초기화
cred = credentials.Certificate("global-culture-lecture-firebase-adminsdk-5cufe-fd85fa5267.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# OpenAI API 설정
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.post("/transcribe_and_translate/")
async def transcribe_and_translate(file: UploadFile = File(...), username: str = Form(...), target_language: str = Form(...)):
    try:
        # 임시 파일로 저장
        with open(file.filename, "wb") as buffer:
            buffer.write(await file.read())
        
        # Whisper API를 사용하여 음성을 텍스트로 변환 및 번역
        with open(file.filename, "rb") as audio_file:
            transcript = openai.Audio.translate("whisper-1", audio_file, target_language)
        
        translated_text = transcript["text"]
        
        # 원본 텍스트 추출 (옵션)
        original_text = extract_original_text(file.filename)
        
        # Firestore에 저장
        save_to_firestore(username, original_text, translated_text, target_language)
        
        # 임시 파일 삭제
        os.remove(file.filename)
        
        return {"original_text": original_text, "translated_text": translated_text}
    except Exception as e:
        return {"error": str(e)}

def extract_original_text(filename):
    # Whisper API를 사용하여 원본 텍스트 추출 (옵션)
    with open(filename, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return transcript["text"]

def save_to_firestore(username, original_text, translated_text, target_language):
    user_doc_ref = db.collection('users').document(username)
    user_doc = user_doc_ref.get()
    
    new_transcription = {
        'original_text': original_text,
        'translated_text': translated_text,
        'target_language': target_language,
        'timestamp': datetime.now(pytz.utc)
    }
    
    if user_doc.exists:
        user_doc_ref.update({
            'transcriptions': firestore.ArrayUnion([new_transcription])
        })
    else:
        user_doc_ref.set({
            'transcriptions': [new_transcription]
        })

@app.get("/get_transcriptions/")
async def get_transcriptions(username: str):
    user_doc_ref = db.collection('users').document(username)
    user_doc = user_doc_ref.get()
    if user_doc.exists:
        transcriptions = user_doc.to_dict().get('transcriptions', [])
        return {"transcriptions": transcriptions}
    else:
        return {"message": f"No transcriptions found for user {username}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
