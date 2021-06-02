from datetime import datetime
import json
import os
import sys
from pathlib import Path
from random import randint

from annoy import AnnoyIndex
from django.utils import timezone
import numpy as np
from PIL import Image
import redis
from redis_lock import Lock

from photonix.classifiers.base_model import BaseModel
from photonix.classifiers.face.deepface import DeepFace
from photonix.classifiers.face.mtcnn import MTCNN
from photonix.classifiers.face.deepface.commons.distance import findEuclideanDistance


GRAPH_FILE = os.path.join('face', 'mtcnn_weights.npy')
DISTANCE_THRESHOLD = 10


class FaceDetectionModel(BaseModel):
    name = 'face'
    version = 20210528
    approx_ram_mb = 600
    max_num_workers = 1

    def __init__(self, model_dir=None, graph_file=GRAPH_FILE, lock_name=None):
        super().__init__(model_dir=model_dir)

        graph_file = os.path.join(self.model_dir, graph_file)

        if self.ensure_downloaded(lock_name=lock_name):
            self.graph = self.load_graph(graph_file)

    def load_graph(self, graph_file):
        r = redis.Redis(host=os.environ.get('REDIS_HOST', '127.0.0.1'))
        with Lock(r, 'classifier_{}_load_graph'.format(self.name)):
            if self.graph_cache_key in self.graph_cache:
                return self.graph_cache[self.graph_cache_key]

            graph = MTCNN(weights_file=graph_file)

            self.graph_cache[self.graph_cache_key] = graph
            return graph

    def predict(self, image_file, min_score=0.99):
        image = Image.open(image_file)
        image = np.asarray(image)
        results = self.graph.detect_faces(image)
        return list(filter(lambda f: f['confidence'] > min_score, results))


def find_closest_face_tag(library_id, source_embedding):
    # Use ANN index to do quick serach if it has been trained by retrain_face_similarity_index
    from django.conf import settings
    ann_path = Path(settings.MODEL_DIR) / 'face' / 'faces.ann'
    tag_ids_path = Path(settings.MODEL_DIR) / 'face' / 'faces_tag_ids.json'

    if os.path.exists(ann_path) and os.path.exists(tag_ids_path):
        embedding_size = 128  # FaceNet output size
        t = AnnoyIndex(embedding_size, 'euclidean')
        # Ensure ANN index, tag IDs and version files can't be updated while we are reading
        r = redis.Redis(host=os.environ.get('REDIS_HOST', '127.0.0.1'))
        with Lock(r, 'face_model_retrain'):
            t.load(str(ann_path))
            with open(tag_ids_path) as f:
                tag_ids = json.loads(f.read())
        nearest = t.get_nns_by_vector(source_embedding, 1, include_distances=True)
        return tag_ids[nearest[0][0]], nearest[1][0]

    # Collect all previously generated embeddings
    from photonix.photos.models import PhotoTag
    representations = []
    for photo_tag in PhotoTag.objects.filter(photo__library_id=library_id, tag__type='F'):
        try:
            tag_embedding = json.loads(photo_tag.extra_data)['facenet_embedding']
            representations.append((str(photo_tag.tag.id), tag_embedding))
        except (KeyError, json.decoder.JSONDecodeError):
            pass

    # Calculate Euclidean distances
    distances = []
    for (_, target_embedding) in representations:
        distance = findEuclideanDistance(source_embedding, target_embedding)
        distances.append(distance)

    # Return closest match and distance value
    if not distances:  # First face has nothing to compare to
        return (None, 999)
    candidate_idx = np.argmin(distances)
    return (representations[candidate_idx][0], distances[candidate_idx])


def get_retrained_model_version():
    from django.conf import settings
    version_file = Path(settings.MODEL_DIR) / 'face' / 'retrained_version.txt'
    version_date = None
    if os.path.exists(version_file):
        with open(version_file) as f:
            contents = f.read().strip()
            version_date = datetime.strptime(contents, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            return int(version_date.strftime('%Y%m%d%H%M%S'))
    return 0


def run_on_photo(photo_id):
    model = FaceDetectionModel()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from photonix.classifiers.runners import results_for_model_on_photo, get_or_create_tag
    # Detect all faces in an image
    photo, results = results_for_model_on_photo(model, photo_id)

    # Read image data so we can extract faces and create embeddings
    path = photo_id
    if photo:
        path = photo.base_image_path
    image_data = Image.open(path)

    # Loop over each face that was detected above
    for result in results:
        # Crop individual face + 30% extra in each direction
        box = result['box']
        face_image = image_data.crop([
            max(box[0]-int(box[2]*0.3), 0),
            max(box[1]-int(box[3]*0.3), 0),
            min(box[0]+box[2]+int(box[2]*0.3), image_data.width),
            min(box[1]+box[3]+int(box[3]*0.3), image_data.height)
        ])
        # Generate embedding with Facenet
        try:
            embedding = DeepFace.represent(np.asarray(face_image), model_name='Facenet')
            # Add it to the results
            result['embedding'] = embedding
            if photo:
                closest_tag, closest_distance = find_closest_face_tag(photo.library, embedding)
                if closest_tag:
                    print(f'Closest tag: {closest_tag}')
                    print(f'Closest distance: {closest_distance}')
                    result['closest_tag'] = closest_tag
                    result['closest_distance'] = closest_distance
        except ValueError:
            pass

    if photo:
        from django.utils import timezone
        from photonix.photos.models import Tag, PhotoTag
        photo.clear_tags(source='C', type='F')
        for result in results:
            if result.get('closest_distance', 999) < DISTANCE_THRESHOLD:
                tag = Tag.objects.get(id=result['closest_tag'], library=photo.library, type='F')
                print(f'MATCHED {tag.name}')
            else:
                tag = get_or_create_tag(library=photo.library, name=f'Unknown person {randint(0, 999999):06d}', type='F', source='C')
            x = (result['box'][0] + (result['box'][2] / 2)) / photo.base_file.width
            y = (result['box'][1] + (result['box'][3] / 2)) / photo.base_file.height
            width = result['box'][2] / photo.base_file.width
            height = result['box'][3] / photo.base_file.height
            score = result['confidence']

            extra_data = ''
            if 'embedding' in result:
                extra_data = json.dumps({'facenet_embedding': result['embedding']})

            PhotoTag(photo=photo, tag=tag, source='F', confidence=score, significance=score, position_x=x, position_y=y, size_x=width, size_y=height, model_version=model.version, retrained_model_version=get_retrained_model_version(), extra_data=extra_data).save()
        photo.classifier_color_completed_at = timezone.now()
        photo.classifier_color_version = getattr(model, 'version', 0)
        photo.save()

    print('Finished')

    return photo, results


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Argument required: image file path or Photo ID')
        exit(1)

    _, results = run_on_photo(sys.argv[1])
    print(results)
