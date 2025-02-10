import face_recognition
import pickle
import asyncio
import numpy as np
from io import BytesIO
import sys
import json

class FaceComparer:
    def __init__(self, encoding_cache_file="encodings.pkl", imgs_folder="/home/duzho/Desktop/duzhobots/face_comparer/imgs_storage/"):
        self.encoding_cache_file = encoding_cache_file
        self.imgs_folder = imgs_folder

    async def load_encodings(self):
        try:
            with open(self.encoding_cache_file, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading encodings: {e}.")
            return {}

    async def compare_faces(self, img_bytes):
        try:
            img = face_recognition.load_image_file(BytesIO(img_bytes))
            img_encoding = face_recognition.face_encodings(img)
            if not img_encoding:
                return [], "No faces found in the image"
            img_encoding = img_encoding[0]
        except Exception as e:
            return [], f"Error processing image: {e}"

        encodings_cache = await self.load_encodings()
        comparison_encodings = np.array([encoding for encoding in encodings_cache.values()])
        image_paths_in_storage = list(encodings_cache.keys())

        if not comparison_encodings.size:
            return [], "No encodings in the cache to compare against"

        distances = face_recognition.face_distance(comparison_encodings, img_encoding)
        results = {path: 100 * (1 - dist) for path, dist in zip(image_paths_in_storage, distances)}
        sorted_results = sorted(results.items(), key=lambda item: item[1], reverse=True)

        top_10_matches_with_scores = []
        for path, sim in sorted_results[:10]:
            top_10_matches_with_scores.append({"path": self.imgs_folder + path, "similarity": f"{sim:.2f}%"})

        return top_10_matches_with_scores, None

async def main():
    file_data = sys.stdin.buffer.read()
    face_comparer = FaceComparer()
    paths_with_scores, err = await face_comparer.compare_faces(file_data)
    if err:
        result = {"error": err}
    else:
        result = {"matches": paths_with_scores}

    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())