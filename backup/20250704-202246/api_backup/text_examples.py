from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.text_example import TextExample
from app.models.profile import Profile
from app.extensions import db

text_examples_bp = Blueprint('text_examples', __name__)

@text_examples_bp.route('', methods=['POST'])
@jwt_required()
def create_text_example():
    user_id = get_jwt_identity()
    data = request.json
    
    # Validate required fields
    if not all([data.get('profile_id'), data.get('content')]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Verify profile ownership
    profile = Profile.query.get_or_404(data['profile_id'])
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Create text example
    example = TextExample(
        profile_id=data['profile_id'],
        content=data['content'],
        is_incoming=data.get('is_incoming', False)
    )
    
    db.session.add(example)
    db.session.commit()
    
    return jsonify(example.to_dict()), 201


@text_examples_bp.route('/<int:example_id>', methods=['DELETE'])
@jwt_required()
def delete_text_example(example_id):
    user_id = get_jwt_identity()
    
    # Find text example
    example = TextExample.query.get_or_404(example_id)
    
    # Verify profile ownership
    profile = Profile.query.get(example.profile_id)
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Delete example
    db.session.delete(example)
    db.session.commit()
    
    return jsonify({"success": True, "message": "Text example deleted"}), 200


@text_examples_bp.route('/bulk', methods=['POST'])
@jwt_required()
def bulk_create_text_examples():
    user_id = get_jwt_identity()
    data = request.json
    
    # Validate required fields
    if not all([data.get('profile_id'), data.get('examples')]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Verify profile ownership
    profile = Profile.query.get_or_404(data['profile_id'])
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Create text examples
    examples = []
    for ex in data['examples']:
        if 'content' not in ex:
            continue
            
        example = TextExample(
            profile_id=data['profile_id'],
            content=ex['content'],
            is_incoming=ex.get('is_incoming', False)
        )
        db.session.add(example)
        examples.append(example)
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": f"Added {len(examples)} text examples",
        "examples": [ex.to_dict() for ex in examples]
    }), 201