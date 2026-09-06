import pytest
from model.predict import predict_comment_detail, predict_comments_batch, detect_threats_and_slurs

def test_benign_comment():
    res = predict_comment_detail("Great video! Really enjoyed watching this content.")
    assert res["is_toxic"] is False
    assert res["label"] == "Non-Toxic"
    assert res["threat_detected"] is False

def test_threat_detection_kys():
    is_toxic, cat, conf = detect_threats_and_slurs("kys right now")
    assert is_toxic is True
    assert "Severe Threat" in cat
    assert conf == 0.99

def test_hinglish_profanity():
    is_toxic, cat, conf = detect_threats_and_slurs("tu chinaar hai")
    assert is_toxic is True
    assert cat == "Hinglish/Hindi Profanity & Slurs"

def test_batch_predictions():
    comments = [
        "Love this video!",
        "kys",
        "This is an informative tutorial"
    ]
    results = predict_comments_batch(comments)
    assert len(results) == 3
    assert results[0]["is_toxic"] is False
    assert results[1]["is_toxic"] is True
    assert results[1]["threat_detected"] is True
    assert results[2]["is_toxic"] is False
