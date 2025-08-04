

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.analytics_queries import get_user_analytics_data  # Import your new query functions

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_analytics():
    """
    Get dashboard analytics for current user
    GET /api/analytics/dashboard?period=7d
    """
    try:
        # Get current user from JWT token
        current_user_id = get_jwt_identity()
        
        # Get period parameter (defaults to 7d)
        period = request.args.get('period', '7d')
        
        # Validate period parameter
        valid_periods = ['24h', '7d', '30d']
        if period not in valid_periods:
            return jsonify({
                'success': False,
                'error': 'Invalid period. Must be one of: 24h, 7d, 30d'
            }), 400
        
        # Call your database query function
        analytics_data = get_user_analytics_data(current_user_id, period)
        
        return jsonify(analytics_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Analytics dashboard error for user {current_user_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch analytics data'
        }), 500

@analytics_bp.route('/messages', methods=['GET'])
@jwt_required()
def get_message_analytics():
    """Get detailed message analytics"""
    try:
        current_user_id = get_jwt_identity()
        period = request.args.get('period', '30d')
        breakdown = request.args.get('breakdown', 'daily')
        
        # You can add more specific message analytics here if needed
        # For now, redirect to dashboard data
        analytics_data = get_user_analytics_data(current_user_id, period)
        
        return jsonify({
            'success': True,
            'data': analytics_data.get('messages', {})
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Message analytics error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch message analytics'
        }), 500

@analytics_bp.route('/clients', methods=['GET'])
@jwt_required()
def get_client_analytics():
    """Get client analytics"""
    try:
        current_user_id = get_jwt_identity()
        period = request.args.get('period', '30d')
        
        analytics_data = get_user_analytics_data(current_user_id, period)
        
        return jsonify({
            'success': True,
            'data': analytics_data.get('client_activity', [])
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Client analytics error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch client analytics'
        }), 500

@analytics_bp.route('/export', methods=['POST'])
@jwt_required()
def export_analytics():
    """Export analytics data"""
    try:
        current_user_id = get_jwt_identity()
        
        # Get export parameters
        export_data = request.get_json()
        export_type = export_data.get('type', 'csv')
        period = export_data.get('period', '7d')
        sections = export_data.get('sections', ['dashboard'])
        
        # Get the analytics data
        analytics_data = get_user_analytics_data(current_user_id, period)
        
        if export_type == 'csv':
            # Convert to CSV format
            csv_data = convert_analytics_to_csv(analytics_data, sections)
            return jsonify({
                'success': True,
                'data': csv_data,
                'filename': f'analytics-{period}-{current_user_id}.csv'
            }), 200
        else:
            return jsonify({
                'success': True,
                'data': analytics_data
            }), 200
            
    except Exception as e:
        current_app.logger.error(f"Export analytics error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to export analytics'
        }), 500

def convert_analytics_to_csv(analytics_data, sections):
    """Convert analytics data to CSV format"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers and data based on sections requested
    if 'dashboard' in sections:
        writer.writerow(['Metric', 'Value'])
        core_metrics = analytics_data.get('core_metrics', {})
        for key, value in core_metrics.items():
            writer.writerow([key.replace('_', ' ').title(), value])
        writer.writerow([])  # Empty row
    
    if 'time_series' in sections:
        writer.writerow(['Date', 'Total Messages', 'Sent', 'Received', 'AI Generated'])
        time_series = analytics_data.get('time_series', [])
        for entry in time_series:
            writer.writerow([
                entry.get('date', ''),
                entry.get('total', 0),
                entry.get('sent', 0),
                entry.get('received', 0),
                entry.get('ai_generated', 0)
            ])
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content