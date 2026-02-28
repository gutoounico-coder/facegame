from flask import Flask, render_template, request, redirect, url_for
import os
import cv2
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ===============================
# CONFIGURAÇÕES
# ===============================

UPLOAD_FOLDER = "static/uploads"
PROCESSED_FOLDER = "static/processed"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER

# cria pastas automaticamente se não existirem
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# ===============================
# BANCO DE DADOS
# ===============================

def init_db():
    conn = sqlite3.connect("scores.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ranking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            filename TEXT,
            score INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ===============================
# FUNÇÕES AUXILIARES
# ===============================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS

def emoji_emocao(emocao):
    emojis = {
        "Feliz":"😄",
        "Triste":"😢",
        "Bravo":"😠",
        "Surpreso":"😲",
        "Neutro":"😐"
    }
    return emojis.get(emocao,"🙂")

def analisar_rosto(caminho_imagem, filename):
    img = cv2.imread(caminho_imagem)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")

    faces = face_cascade.detectMultiScale(gray,1.3,5)
    olhos_detectados = 0
    sorriso_detectado = False

    for (x,y,w,h) in faces:
        cv2.rectangle(img,(x,y),(x+w,y+h),(0,255,0),3)
        roi_gray = gray[y:y+h, x:x+w]
        roi_color = img[y:y+h, x:x+w]

        olhos = eye_cascade.detectMultiScale(roi_gray,1.1,10)
        olhos_detectados = len(olhos)
        for (ex,ey,ew,eh) in olhos:
            cv2.rectangle(roi_color,(ex,ey),(ex+ew,ey+eh),(255,0,0),2)

        sorrisos = smile_cascade.detectMultiScale(roi_gray,1.7,22)
        if len(sorrisos) > 0:
            sorriso_detectado = True
        for (sx,sy,sw,sh) in sorrisos:
            cv2.rectangle(roi_color,(sx,sy),(sx+sw,sy+sh),(0,0,255),2)

    # Score
    score = 5
    if len(faces) > 0: score += 2
    if olhos_detectados >= 2: score += 2
    if sorriso_detectado: score += 1
    score = min(score,10)

    output_path = os.path.join(app.config["PROCESSED_FOLDER"], filename)
    cv2.imwrite(output_path,img)

    return score

# ===============================
# ROTAS
# ===============================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    nome = request.form.get("nome")
    if not nome: nome = "Anonimo"

    if "file" not in request.files:
        return "Nenhum arquivo enviado"

    file = request.files["file"]
    if file.filename == "":
        return "Arquivo vazio"

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        print("Imagem salva em:", filepath)
        return redirect(url_for("analisando", filename=filename, nome=nome))

    return "Formato não permitido"

@app.route("/analisando/<filename>")
def analisando(filename):
    nome = request.args.get("nome","Anonimo")
    return render_template("analisando.html", filename=filename, nome=nome)

@app.route("/resultado/<filename>")
def resultado(filename):
    nome = request.args.get("nome","Anonimo")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    score = analisar_rosto(filepath, filename)

    # Salva no banco
    conn = sqlite3.connect("scores.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ranking (nome, filename, score) VALUES (?,?,?)",(nome,filename,score))
    conn.commit()
    conn.close()

    image_url = url_for("static", filename=f"processed/{filename}")
    return render_template("resultado.html", image_url=image_url, score=score, nome=nome)

@app.route("/ranking")
def ranking():
    conn = sqlite3.connect("scores.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome, filename, score FROM ranking ORDER BY score DESC LIMIT 10")
    dados = cursor.fetchall()
    conn.close()
    return render_template("ranking.html", dados=dados)

# ===============================
# START
# ===============================

if __name__ == "__main__":
    app.run(debug=True)