from flask import Flask, request, render_template
from model.predict import predict_comment

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        comment = request.form["comment"]
        result = predict_comment(comment)

    return render_template("index.html", result=result)

if __name__ == "__main__":
    app.run(debug=True)