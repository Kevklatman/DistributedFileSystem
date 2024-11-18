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
  Memory as MemoryIcon,
  NetworkCheck as NetworkIcon,
  Warning as WarningIcon,
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
  MonetizationOn as MonetizationOnIcon,
  Savings as SavingsIcon,
  BarChart as BarChartIcon,
  Recommend as RecommendIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = 'http://localhost:5555';

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

const MetricsCard = ({ title, icon, children }) => (
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

const DashboardMetrics = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/dashboard/metrics`);
        setMetrics(response.data);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        Error loading metrics: {error}
      </Alert>
    );
  }

  if (!metrics) {
    return null;
  }

  return (
    <Grid container spacing={3} sx={{ p: 2 }}>
      {/* System Metrics */}
      <Grid item xs={12} md={6}>
        <MetricsCard title="System Health" icon={<SpeedIcon />}>
          <List>
            <ListItem>
              <ListItemIcon>
                <SpeedIcon />
              </ListItemIcon>
              <ListItemText
                primary="CPU Usage"
                secondary={`${metrics.health?.cpu_usage || 0}%`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <MemoryIcon />
              </ListItemIcon>
              <ListItemText
                primary="Memory Usage"
                secondary={`${metrics.health?.memory_usage || 0}%`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <NetworkIcon />
              </ListItemIcon>
              <ListItemText
                primary="Network Bandwidth"
                secondary={`${metrics.health?.network_bandwidth_mbps || 0} MB/s`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                {metrics.health?.status === 'healthy' ? (
                  <HealthyIcon color="success" />
                ) : metrics.health?.status === 'warning' ? (
                  <WarningIcon color="warning" />
                ) : (
                  <ErrorIcon color="error" />
                )}
              </ListItemIcon>
              <ListItemText
                primary="System Status"
                secondary={
                  <Box>
                    <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                      {metrics.health?.status || 'unknown'}
                    </Typography>
                    <Typography variant="body2">
                      Errors: {metrics.health?.error_count || 0}
                    </Typography>
                    <Typography variant="body2">
                      Warnings: {metrics.health?.warning_count || 0}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
          </List>
        </MetricsCard>
      </Grid>

      {/* Storage Metrics */}
      <Grid item xs={12} md={6}>
        <MetricsCard title="Storage Details" icon={<StorageIcon />}>
          <List>
            <ListItem>
              <ListItemIcon>
                <StorageIcon />
              </ListItemIcon>
              <ListItemText
                primary="Storage Usage"
                secondary={`${metrics.storage?.usage_percent || 0}% (${metrics.storage?.used_capacity_gb || 0} GB / ${metrics.storage?.total_capacity_gb || 0} GB)`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <StorageIcon />
              </ListItemIcon>
              <ListItemText
                primary="Available Storage"
                secondary={`${metrics.storage?.available_capacity_gb || 0} GB`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <SpeedIcon />
              </ListItemIcon>
              <ListItemText
                primary="Performance"
                secondary={`IOPS: ${metrics.storage?.iops || 0} | Throughput: ${metrics.storage?.throughput_mbps || 0} MB/s`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <StorageIcon />
              </ListItemIcon>
              <ListItemText
                primary="Efficiency"
                secondary={`Compression: ${metrics.storage?.compression_ratio || 1}x | Dedup: ${metrics.storage?.dedup_ratio || 1}x`}
              />
            </ListItem>
          </List>
        </MetricsCard>
      </Grid>

      {/* Cost Metrics */}
      <Grid item xs={12} md={6}>
        <MetricsCard title="Cost & Savings" icon={<MonetizationOnIcon />}>
          <List>
            <ListItem>
              <ListItemIcon>
                <MonetizationOnIcon />
              </ListItemIcon>
              <ListItemText
                primary="Monthly Cost"
                secondary={`$${metrics.cost?.total_cost_month || 0}`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <SavingsIcon />
              </ListItemIcon>
              <ListItemText
                primary="Total Savings"
                secondary={`$${metrics.cost?.total_savings || 0}`}
              />
            </ListItem>
            <Divider />
            <ListItem>
              <ListItemIcon>
                <BarChartIcon />
              </ListItemIcon>
              <ListItemText
                primary="Savings Breakdown"
                secondary={
                  <Box>
                    <Typography variant="body2">
                      Tiering: ${metrics.cost?.savings_from_tiering || 0}
                    </Typography>
                    <Typography variant="body2">
                      Dedup: ${metrics.cost?.savings_from_dedup || 0}
                    </Typography>
                    <Typography variant="body2">
                      Compression: ${metrics.cost?.savings_from_compression || 0}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
          </List>
        </MetricsCard>
      </Grid>

      {/* Recommendations */}
      <Grid item xs={12}>
        <MetricsCard title="Recommendations" icon={<RecommendIcon />}>
          <List>
            {metrics.recommendations?.map((rec, index) => (
              <ListItem key={index}>
                <ListItemIcon>
                  {rec.severity === 'warning' ? (
                    <WarningIcon color="warning" />
                  ) : (
                    <InfoIcon color="info" />
                  )}
                </ListItemIcon>
                <ListItemText
                  primary={rec.title}
                  secondary={
                    <Box>
                      <Typography variant="body2">{rec.description}</Typography>
                      <Box mt={1}>
                        {rec.suggestions.map((suggestion, idx) => (
                          <Chip
                            key={idx}
                            label={suggestion}
                            size="small"
                            sx={{ mr: 1, mb: 1 }}
                          />
                        ))}
                      </Box>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </MetricsCard>
      </Grid>

      {/* Pod Status */}
      <Grid item xs={12}>
        <MetricsCard title="Pods" icon={<SpeedIcon />}>
          <Grid container spacing={1}>
            {metrics.pods.map((pod) => (
              <Grid item xs={12} sm={6} md={4} key={pod.name}>
                <Card variant="outlined" sx={{ p: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    {pod.status === 'Running' ? (
                      <HealthyIcon color="success" sx={{ mr: 1 }} />
                    ) : (
                      <WarningIcon color="warning" sx={{ mr: 1 }} />
                    )}
                    <Typography variant="subtitle2">{pod.name}</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    Status: {pod.status}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    IP: {pod.ip}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Node: {pod.node}
                  </Typography>
                </Card>
              </Grid>
            ))}
          </Grid>
        </MetricsCard>
      </Grid>
    </Grid>
  );
};

export default DashboardMetrics;
