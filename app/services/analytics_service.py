from app.models.user import User
from app.models.client import Client
from app.models.messaging import Message
from app.models.usage_analytics import UsageAnalytics
from app.models.conversation_analytics import ConversationAnalytics
from app.services.signalwire_service import SignalWireService
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, extract, case, and_, or_, text
from collections import defaultdict
import json
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Service for generating comprehensive analytics across the platform"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.user = User.query.get(user_id)
    
    def get_comprehensive_dashboard_data(self, period='7d', include_predictions=False):
        """
        Generate comprehensive dashboard analytics data
        
        Args:
            period (str): Time period (1d, 7d, 30d, 90d, 1y)
            include_predictions (bool): Include AI predictions for trends
        
        Returns:
            dict: Complete analytics data structure
        """
        try:
            start_date, end_date = self._get_date_range(period)
            
            # Core metrics
            core_metrics = self._get_core_metrics(start_date, end_date)
            
            # Message analytics
            message_analytics = self._get_detailed_message_analytics(start_date, end_date)
            
            # Client analytics
            client_analytics = self._get_detailed_client_analytics(start_date, end_date)
            
            # AI performance analytics
            ai_analytics = self._get_ai_performance_analytics(start_date, end_date)
            
            # Business intelligence
            business_intelligence = self._get_business_intelligence(start_date, end_date)
            
            # Time series data
            time_series = self._get_time_series_data(start_date, end_date, period)
            
            # Growth metrics
            growth_metrics = self._get_growth_metrics(start_date, end_date, period)
            
            # Optional predictions
            predictions = None
            if include_predictions:
                predictions = self._generate_trend_predictions(time_series)
            
            return {
                'success': True,
                'generated_at': datetime.utcnow().isoformat(),
                'period': period,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'core_metrics': core_metrics,
                'messages': message_analytics,
                'clients': client_analytics,
                'ai_performance': ai_analytics,
                'business_intelligence': business_intelligence,
                'time_series': time_series,
                'growth': growth_metrics,
                'predictions': predictions
            }
            
        except Exception as e:
            logger.error(f"Error generating dashboard data: {str(e)}")
            raise
    
    def get_advanced_message_analytics(self, period='30d', breakdown_type='daily'):
        """
        Advanced message analytics with detailed breakdowns
        
        Args:
            period (str): Time period for analysis
            breakdown_type (str): 'hourly', 'daily', 'weekly', 'monthly'
        
        Returns:
            dict: Detailed message analytics
        """
        start_date, end_date = self._get_date_range(period)
        
        # Volume analytics
        volume_data = self._get_message_volume_analytics(start_date, end_date, breakdown_type)
        
        # Performance analytics
        performance_data = self._get_message_performance_analytics(start_date, end_date)
        
        # Content analytics
        content_analysis = self._get_message_content_analytics(start_date, end_date)
        
        # Response pattern analysis
        response_patterns = self._get_response_pattern_analysis(start_date, end_date)
        
        # Delivery analytics
        delivery_analytics = self._get_delivery_analytics(start_date, end_date)
        
        return {
            'volume': volume_data,
            'performance': performance_data,
            'content': content_analysis,
            'patterns': response_patterns,
            'delivery': delivery_analytics
        }
    
    def get_client_intelligence_report(self, period='30d'):
        """
        Comprehensive client intelligence and segmentation
        
        Args:
            period (str): Analysis period
        
        Returns:
            dict: Client intelligence data
        """
        start_date, end_date = self._get_date_range(period)
        
        # Client lifecycle analysis
        lifecycle_data = self._get_client_lifecycle_analysis(start_date, end_date)
        
        # Engagement scoring
        engagement_data = self._get_client_engagement_scoring(start_date, end_date)
        
        # Risk analysis
        risk_analysis = self._get_client_risk_analysis(start_date, end_date)
        
        # Value analysis
        value_analysis = self._get_client_value_analysis(start_date, end_date)
        
        # Behavioral patterns
        behavioral_patterns = self._get_client_behavioral_patterns(start_date, end_date)
        
        # Segmentation recommendations
        segmentation = self._get_intelligent_client_segmentation(start_date, end_date)
        
        return {
            'lifecycle': lifecycle_data,
            'engagement': engagement_data,
            'risk_analysis': risk_analysis,
            'value_analysis': value_analysis,
            'behavioral_patterns': behavioral_patterns,
            'segmentation': segmentation
        }
    
    def get_ai_performance_deep_dive(self, period='30d'):
        """
        Deep dive into AI performance and optimization opportunities
        
        Args:
            period (str): Analysis period
        
        Returns:
            dict: AI performance analysis
        """
        start_date, end_date = self._get_date_range(period)
        
        # AI effectiveness metrics
        effectiveness = self._get_ai_effectiveness_metrics(start_date, end_date)
        
        # Response quality analysis
        quality_analysis = self._get_ai_response_quality_analysis(start_date, end_date)
        
        # Learning curve analysis
        learning_curve = self._get_ai_learning_curve_analysis(start_date, end_date)
        
        # Optimization recommendations
        optimization_recs = self._get_ai_optimization_recommendations(start_date, end_date)
        
        # Confidence score analysis
        confidence_analysis = self._get_ai_confidence_analysis(start_date, end_date)
        
        return {
            'effectiveness': effectiveness,
            'quality': quality_analysis,
            'learning_curve': learning_curve,
            'optimization': optimization_recs,
            'confidence': confidence_analysis
        }
    
    def generate_business_insights_report(self, period='90d'):
        """
        Generate actionable business insights and recommendations
        
        Args:
            period (str): Analysis period
        
        Returns:
            dict: Business insights and recommendations
        """
        start_date, end_date = self._get_date_range(period)
        
        # Revenue impact analysis
        revenue_impact = self._analyze_revenue_impact(start_date, end_date)
        
        # Efficiency improvements
        efficiency_analysis = self._analyze_efficiency_opportunities(start_date, end_date)
        
        # Client satisfaction indicators
        satisfaction_metrics = self._analyze_client_satisfaction(start_date, end_date)
        
        # Growth opportunities
        growth_opportunities = self._identify_growth_opportunities(start_date, end_date)
        
        # Risk factors
        risk_factors = self._identify_risk_factors(start_date, end_date)
        
        # Actionable recommendations
        recommendations = self._generate_actionable_recommendations(
            revenue_impact, efficiency_analysis, satisfaction_metrics, 
            growth_opportunities, risk_factors
        )
        
        return {
            'revenue_impact': revenue_impact,
            'efficiency': efficiency_analysis,
            'satisfaction': satisfaction_metrics,
            'growth_opportunities': growth_opportunities,
            'risk_factors': risk_factors,
            'recommendations': recommendations
        }
    
    # CORE HELPER METHODS
    
    def _get_date_range(self, period):
        """Calculate start and end dates for given period"""
        end_date = datetime.utcnow()
        
        if period == '1d':
            start_date = end_date - timedelta(days=1)
        elif period == '7d':
            start_date = end_date - timedelta(days=7)
        elif period == '30d':
            start_date = end_date - timedelta(days=30)
        elif period == '90d':
            start_date = end_date - timedelta(days=90)
        elif period == '1y':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=7)
        
        return start_date, end_date
    
    def _get_core_metrics(self, start_date, end_date):
        """Get core platform metrics"""
        
        # Message counts
        total_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).count()
        
        sent_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.is_incoming == False,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).count()
        
        received_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.is_incoming == True,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).count()
        
        ai_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.ai_generated == True,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).count()
        
        # Client metrics
        total_clients = Client.query.filter(Client.user_id == self.user_id).count()
        
        active_clients = db.session.query(Client.id).join(Message).filter(
            Client.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).distinct().count()
        
        new_clients = Client.query.filter(
            Client.user_id == self.user_id,
            Client.created_at >= start_date,
            Client.created_at <= end_date
        ).count()
        
        # Calculate rates
        ai_adoption_rate = (ai_messages / sent_messages * 100) if sent_messages > 0 else 0
        response_rate = (sent_messages / received_messages * 100) if received_messages > 0 else 0
        client_activity_rate = (active_clients / total_clients * 100) if total_clients > 0 else 0
        
        # Get average response time from conversation analytics
        avg_response_time = db.session.query(
            func.avg(ConversationAnalytics.avg_response_time)
        ).filter(
            ConversationAnalytics.user_id == self.user_id,
            ConversationAnalytics.updated_at >= start_date
        ).scalar() or 0
        
        return {
            'total_messages': total_messages,
            'sent_messages': sent_messages,
            'received_messages': received_messages,
            'ai_messages': ai_messages,
            'total_clients': total_clients,
            'active_clients': active_clients,
            'new_clients': new_clients,
            'ai_adoption_rate': round(ai_adoption_rate, 2),
            'response_rate': round(response_rate, 2),
            'client_activity_rate': round(client_activity_rate, 2),
            'avg_response_time_minutes': round(float(avg_response_time or 0) / 60, 1)
        }
    
    def _get_detailed_message_analytics(self, start_date, end_date):
        """Get detailed message analytics"""
        
        # Message types breakdown
        message_types = db.session.query(
            func.count(case([(Message.is_incoming == True, 1)])).label('incoming'),
            func.count(case([(Message.is_incoming == False, 1)])).label('outgoing'),
            func.count(case([(Message.ai_generated == True, 1)])).label('ai_generated'),
            func.count(case([(and_(Message.is_incoming == False, Message.ai_generated == False), 1)])).label('manual')
        ).filter(
            Message.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).first()
        
        # Message status breakdown (if you track delivery status)
        status_breakdown = db.session.query(
            Message.status,
            func.count(Message.id)
        ).filter(
            Message.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date,
            Message.status.isnot(None)
        ).group_by(Message.status).all()
        
        # Peak messaging hours
        hourly_breakdown = db.session.query(
            extract('hour', Message.timestamp).label('hour'),
            func.count(Message.id).label('count')
        ).filter(
            Message.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).group_by(extract('hour', Message.timestamp)).all()
        
        peak_hours = sorted(hourly_breakdown, key=lambda x: x.count, reverse=True)[:3]
        
        # Average message length
        avg_length = db.session.query(
            func.avg(func.length(Message.message_body))
        ).filter(
            Message.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date,
            Message.message_body.isnot(None)
        ).scalar() or 0
        
        return {
            'types': {
                'incoming': message_types.incoming or 0,
                'outgoing': message_types.outgoing or 0,
                'ai_generated': message_types.ai_generated or 0,
                'manual': message_types.manual or 0
            },
            'status_breakdown': {status: count for status, count in status_breakdown},
            'peak_hours': [{'hour': hour, 'count': count} for hour, count in peak_hours],
            'avg_message_length': round(float(avg_length), 1)
        }
    
    def _get_detailed_client_analytics(self, start_date, end_date):
        """Get detailed client analytics"""
        
        # Client type distribution
        client_types = db.session.query(
            Client.client_type,
            func.count(Client.id)
        ).filter(Client.user_id == self.user_id).group_by(Client.client_type).all()
        
        # Client engagement levels
        engagement_levels = db.session.query(
            case([
                (ConversationAnalytics.engagement_score >= 0.8, 'high'),
                (ConversationAnalytics.engagement_score >= 0.5, 'medium'),
                (ConversationAnalytics.engagement_score < 0.5, 'low')
            ]).label('engagement_level'),
            func.count(ConversationAnalytics.id)
        ).filter(
            ConversationAnalytics.user_id == self.user_id,
            ConversationAnalytics.updated_at >= start_date
        ).group_by('engagement_level').all()
        
        # Client acquisition trend
        daily_acquisitions = db.session.query(
            func.date(Client.created_at).label('date'),
            func.count(Client.id).label('new_clients')
        ).filter(
            Client.user_id == self.user_id,
            Client.created_at >= start_date,
            Client.created_at <= end_date
        ).group_by(func.date(Client.created_at)).all()
        
        # Client retention (active in last 7 days)
        retention_cutoff = end_date - timedelta(days=7)
        recent_active = db.session.query(Client.id).join(Message).filter(
            Client.user_id == self.user_id,
            Message.timestamp >= retention_cutoff
        ).distinct().count()
        
        total_clients = Client.query.filter(Client.user_id == self.user_id).count()
        retention_rate = (recent_active / total_clients * 100) if total_clients > 0 else 0
        
        return {
            'type_distribution': {client_type: count for client_type, count in client_types},
            'engagement_levels': {level: count for level, count in engagement_levels},
            'acquisition_trend': [
                {'date': date.isoformat(), 'new_clients': count} 
                for date, count in daily_acquisitions
            ],
            'retention_rate': round(retention_rate, 2),
            'active_clients_7d': recent_active
        }
    
    def _get_ai_performance_analytics(self, start_date, end_date):
        """Get AI performance analytics"""
        
        # AI usage rate over time
        daily_ai_usage = db.session.query(
            func.date(Message.timestamp).label('date'),
            func.count(case([(Message.ai_generated == True, 1)])).label('ai_messages'),
            func.count(case([(Message.is_incoming == False, 1)])).label('total_outgoing')
        ).filter(
            Message.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).group_by(func.date(Message.timestamp)).all()
        
        # AI confidence scores
        confidence_stats = db.session.query(
            func.avg(Message.ai_confidence).label('avg_confidence'),
            func.min(Message.ai_confidence).label('min_confidence'),
            func.max(Message.ai_confidence).label('max_confidence')
        ).filter(
            Message.user_id == self.user_id,
            Message.ai_generated == True,
            Message.ai_confidence.isnot(None),
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).first()
        
        # AI response time (if tracked)
        ai_response_times = db.session.query(
            func.avg(Message.processing_time).label('avg_processing_time')
        ).filter(
            Message.user_id == self.user_id,
            Message.ai_generated == True,
            Message.processing_time.isnot(None),
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).scalar()
        
        return {
            'usage_trend': [
                {
                    'date': date.isoformat(),
                    'ai_messages': ai_count,
                    'total_outgoing': total_count,
                    'ai_rate': round((ai_count / total_count * 100) if total_count > 0 else 0, 2)
                }
                for date, ai_count, total_count in daily_ai_usage
            ],
            'confidence_stats': {
                'avg_confidence': round(float(confidence_stats.avg_confidence or 0), 2),
                'min_confidence': round(float(confidence_stats.min_confidence or 0), 2),
                'max_confidence': round(float(confidence_stats.max_confidence or 0), 2)
            },
            'avg_processing_time_ms': round(float(ai_response_times or 0), 1)
        }
    
    def _get_business_intelligence(self, start_date, end_date):
        """Get business intelligence metrics"""
        
        # Calculate cost savings from AI (if you track costs)
        total_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.is_incoming == False,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).count()
        
        ai_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.ai_generated == True,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).count()
        
        # Estimate time savings (assuming 2 minutes per manual response)
        estimated_time_saved_minutes = ai_messages * 2
        estimated_time_saved_hours = estimated_time_saved_minutes / 60
        
        # Client satisfaction proxy (response rate and sentiment)
        avg_sentiment = db.session.query(
            func.avg(ConversationAnalytics.sentiment_score)
        ).filter(
            ConversationAnalytics.user_id == self.user_id,
            ConversationAnalytics.updated_at >= start_date
        ).scalar() or 0
        
        # Communication efficiency
        avg_response_time = db.session.query(
            func.avg(ConversationAnalytics.avg_response_time)
        ).filter(
            ConversationAnalytics.user_id == self.user_id,
            ConversationAnalytics.updated_at >= start_date
        ).scalar() or 0
        
        return {
            'automation_rate': round((ai_messages / total_messages * 100) if total_messages > 0 else 0, 2),
            'estimated_time_saved_hours': round(estimated_time_saved_hours, 1),
            'avg_sentiment_score': round(float(avg_sentiment), 2),
            'avg_response_time_minutes': round(float(avg_response_time or 0) / 60, 1),
            'total_automated_responses': ai_messages
        }
    
    def _get_time_series_data(self, start_date, end_date, period):
        """Get time series data based on period"""
        
        if period == '1d':
            # Hourly data for 1 day
            return self._get_hourly_time_series(start_date, end_date)
        elif period in ['7d', '30d']:
            # Daily data
            return self._get_daily_time_series(start_date, end_date)
        else:
            # Weekly data for longer periods
            return self._get_weekly_time_series(start_date, end_date)
    
    def _get_daily_time_series(self, start_date, end_date):
        """Get daily time series data"""
        
        daily_data = db.session.query(
            func.date(Message.timestamp).label('date'),
            func.count(case([(Message.is_incoming == False, 1)])).label('sent'),
            func.count(case([(Message.is_incoming == True, 1)])).label('received'),
            func.count(case([(Message.ai_generated == True, 1)])).label('ai_generated')
        ).filter(
            Message.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).group_by(func.date(Message.timestamp)).order_by(func.date(Message.timestamp)).all()
        
        return [
            {
                'date': date.isoformat(),
                'sent': sent,
                'received': received,
                'ai_generated': ai_generated,
                'total': sent + received
            }
            for date, sent, received, ai_generated in daily_data
        ]
    
    def _get_growth_metrics(self, start_date, end_date, period):
        """Calculate growth metrics compared to previous period"""
        
        # Calculate previous period
        period_length = end_date - start_date
        previous_start = start_date - period_length
        previous_end = start_date
        
        # Current period metrics
        current_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).count()
        
        current_clients = Client.query.filter(
            Client.user_id == self.user_id,
            Client.created_at >= start_date,
            Client.created_at <= end_date
        ).count()
        
        current_ai_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.ai_generated == True,
            Message.timestamp >= start_date,
            Message.timestamp <= end_date
        ).count()
        
        # Previous period metrics
        previous_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.timestamp >= previous_start,
            Message.timestamp <= previous_end
        ).count()
        
        previous_clients = Client.query.filter(
            Client.user_id == self.user_id,
            Client.created_at >= previous_start,
            Client.created_at <= previous_end
        ).count()
        
        previous_ai_messages = Message.query.filter(
            Message.user_id == self.user_id,
            Message.ai_generated == True,
            Message.timestamp >= previous_start,
            Message.timestamp <= previous_end
        ).count()
        
        # Calculate growth rates
        def calc_growth_rate(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 2)
        
        return {
            'message_growth': calc_growth_rate(current_messages, previous_messages),
            'client_growth': calc_growth_rate(current_clients, previous_clients),
            'ai_usage_growth': calc_growth_rate(current_ai_messages, previous_ai_messages),
            'current_period': {
                'messages': current_messages,
                'clients': current_clients,
                'ai_messages': current_ai_messages
            },
            'previous_period': {
                'messages': previous_messages,
                'clients': previous_clients,
                'ai_messages': previous_ai_messages
            }
        }
    
    def get_signalwire_integration_data(self):
        """Get SignalWire specific analytics if configured"""
        
        if not self.user or not self.user.signalwire_configured:
            return None
        
        try:
            signalwire_service = SignalWireService(self.user)
            success, usage_data = signalwire_service.get_usage_statistics()
            
            if success:
                return usage_data
            else:
                logger.warning(f"Failed to get SignalWire data for user {self.user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting SignalWire data: {str(e)}")
            return None
    
    # Additional helper methods would be implemented here...
    # (I've included the core structure - additional methods can be added as needed)
    
    def _get_hourly_time_series(self, start_date, end_date):
        """Get hourly time series data"""
        # Implementation for hourly breakdown
        pass
    
    def _get_weekly_time_series(self, start_date, end_date):
        """Get weekly time series data"""
        # Implementation for weekly breakdown
        pass
    
    def _generate_trend_predictions(self, time_series_data):
        """Generate AI-powered trend predictions"""
        # Implementation for predictions
        pass