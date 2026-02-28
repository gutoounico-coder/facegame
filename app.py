from flask import Flask, render_template, request, redirect, url_for
import os
import cv2
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)

# ===============================
# CONFIGURAÇÕES
# ===============================

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_RECORDS = 100  # limite de registros no banco

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # Limite de upload 2MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def analisar_rosto(caminho_imagem):
    """
    Função otimizada: apenas detecta rosto e calcula score.
    Não salva imagem processada.
    """
    img = cv2.imread(caminho_imagem)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    score = 5
    if len(faces) > 0:
        score += 3

    # Retorna score máximo 10
    return min(score, 10)

# ===============================
# ROTAS
# ===============================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    nome = request.form.get("nome", "Anonimo")

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
    nome = request.args.get("nome", "Anonimo")
    return render_template("analisando.html", filename=filename, nome=nome)

@app.route("/resultado/<filename>")
def resultado(filename):
    nome = request.args.get("nome", "Anonimo")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # Calcula score
    score = analisar_rosto(filepath)

    # ===============================
    # Banco limitado
    # ===============================
    conn = sqlite3.connect("scores.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM ranking")
    total = cursor.fetchone()[0]

    if total >= MAX_RECORDS:
        cursor.execute("""
            DELETE FROM ranking 
            WHERE id = (
                SELECT id FROM ranking ORDER BY id ASC LIMIT 1
            )
        """)

    cursor.execute(
        "INSERT INTO ranking (nome, filename, score) VALUES (?,?,?)",
        (nome, filename, score)
    )
    conn.commit()
    conn.close()

    # URL da imagem (mostrando upload original)
    image_url = url_for("static", filename=f"uploads/{filename}")
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
    # Para produção no Render/Railway use:
    # gunicorn app:app
    app.run(debug=True)