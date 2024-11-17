import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  Grid,
  Typography,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Chip,
} from '@mui/material';
import {
  Storage as StorageIcon,
  Speed as SpeedIcon,
  AttachMoney as MoneyIcon,
  Policy as PolicyIcon,
  Warning as WarningIcon,
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';

interface MetricsCardProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

const MetricsCard: React.FC<MetricsCardProps> = ({ title, icon, children }) => (
  <Card sx={{ p: 2, height: '100%' }}>
    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
      {icon}
      <Typography variant="h6" sx={{ ml: 1 }}>
        {title}
      </Typography>
    </Box>
    {children}
  </Card>
);

const DashboardMetrics: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch('/api/dashboard/metrics');
        if (!response.ok) {
          throw new Error('Failed to fetch metrics');
        }
        const data = await response.json();
        setMetrics(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    // Refresh every 30 seconds
    const interval = setInterval(fetchMetrics, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        Error loading dashboard metrics: {error}
      </Alert>
    );
  }

  const getHealthIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <HealthyIcon sx={{ color: 'success.main' }} />;
      case 'warning':
        return <WarningIcon sx={{ color: 'warning.main' }} />;
      case 'error':
        return <ErrorIcon sx={{ color: 'error.main' }} />;
      default:
        return <HealthyIcon sx={{ color: 'success.main' }} />;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Grid container spacing={3}>
        {/* System Health */}
        <Grid item xs={12} md={6}>
          <MetricsCard
            title="System Health"
            icon={getHealthIcon(metrics.health.status)}
          >
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  CPU Usage
                </Typography>
                <Typography variant="h6">
                  {metrics.health.cpu_usage.toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  Memory Usage
                </Typography>
                <Typography variant="h6">
                  {metrics.health.memory_usage.toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  I/O Latency
                </Typography>
                <Typography variant="h6">
                  {metrics.health.io_latency_ms.toFixed(1)} ms
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  Network Bandwidth
                </Typography>
                <Typography variant="h6">
                  {metrics.health.network_bandwidth_mbps.toFixed(1)} Mbps
                </Typography>
              </Grid>
            </Grid>
          </MetricsCard>
        </Grid>

        {/* Storage Metrics */}
        <Grid item xs={12} md={6}>
          <MetricsCard title="Storage" icon={<StorageIcon color="primary" />}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  Usage
                </Typography>
                <Typography variant="h6">
                  {metrics.storage.usage_percent.toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  Available
                </Typography>
                <Typography variant="h6">
                  {metrics.storage.available_capacity_gb.toFixed(1)} GB
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  Dedup Ratio
                </Typography>
                <Typography variant="h6">
                  {metrics.storage.dedup_ratio.toFixed(2)}x
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  Compression
                </Typography>
                <Typography variant="h6">
                  {metrics.storage.compression_ratio.toFixed(2)}x
                </Typography>
              </Grid>
            </Grid>
          </MetricsCard>
        </Grid>

        {/* Cost Analysis */}
        <Grid item xs={12} md={6}>
          <MetricsCard title="Cost Analysis" icon={<MoneyIcon color="primary" />}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  Monthly Cost
                </Typography>
                <Typography variant="h6">
                  ${metrics.cost.total_cost_month.toFixed(2)}
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  Total Savings
                </Typography>
                <Typography variant="h6" sx={{ color: 'success.main' }}>
                  ${metrics.cost.total_savings.toFixed(2)}
                </Typography>
              </Grid>
              <Grid item xs={12}>
                <Typography variant="body2" color="text.secondary">
                  Cost Trend
                </Typography>
                <Chip
                  label={`${metrics.cost.cost_trend_percent.toFixed(1)}%`}
                  color={metrics.cost.cost_trend_percent > 0 ? 'error' : 'success'}
                  size="small"
                  sx={{ mt: 1 }}
                />
              </Grid>
            </Grid>
          </MetricsCard>
        </Grid>

        {/* Policy Status */}
        <Grid item xs={12} md={6}>
          <MetricsCard title="Policy Engine" icon={<PolicyIcon color="primary" />}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  ML Accuracy
                </Typography>
                <Typography variant="h6">
                  {metrics.policy.ml_policy_accuracy.toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  24h Changes
                </Typography>
                <Typography variant="h6">
                  {metrics.policy.policy_changes_24h}
                </Typography>
              </Grid>
              <Grid item xs={12}>
                <Typography variant="body2" color="text.secondary">
                  Data Moved (24h)
                </Typography>
                <Typography variant="h6">
                  {metrics.policy.data_moved_24h_gb.toFixed(1)} GB
                </Typography>
              </Grid>
            </Grid>
          </MetricsCard>
        </Grid>

        {/* Recommendations */}
        <Grid item xs={12}>
          <Card sx={{ p: 2 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              System Recommendations
            </Typography>
            <List>
              {metrics.recommendations.map((rec: any, index: number) => (
                <React.Fragment key={index}>
                  {index > 0 && <Divider />}
                  <ListItem>
                    <ListItemIcon>
                      {rec.severity === 'warning' ? (
                        <WarningIcon color="warning" />
                      ) : (
                        <ErrorIcon color="error" />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={rec.title}
                      secondary={
                        <>
                          <Typography variant="body2" color="text.secondary">
                            {rec.description}
                          </Typography>
                          <List dense>
                            {rec.suggestions.map((suggestion: string, idx: number) => (
                              <ListItem key={idx}>
                                <ListItemText
                                  primary={`• ${suggestion}`}
                                  primaryTypographyProps={{
                                    variant: 'body2',
                                    color: 'text.secondary',
                                  }}
                                />
                              </ListItem>
                            ))}
                          </List>
                        </>
                      }
                    />
                  </ListItem>
                </React.Fragment>
              ))}
            </List>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardMetrics;
