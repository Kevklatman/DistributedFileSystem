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
} from '@mui/icons-material';

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
        const response = await fetch('/api/metrics');
        if (!response.ok) {
          throw new Error('Failed to fetch metrics');
        }
        const data = await response.json();
        setMetrics(data);
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
        <MetricsCard title="System" icon={<SpeedIcon />}>
          <List>
            <ListItem>
              <ListItemIcon>
                <SpeedIcon />
              </ListItemIcon>
              <ListItemText
                primary="CPU Usage"
                secondary={`${metrics.system.cpu_percent.toFixed(1)}%`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <MemoryIcon />
              </ListItemIcon>
              <ListItemText
                primary="Memory Usage"
                secondary={`${((metrics.system.memory.used / metrics.system.memory.total) * 100).toFixed(1)}%`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <NetworkIcon />
              </ListItemIcon>
              <ListItemText
                primary="Network I/O"
                secondary={`In: ${formatBytes(metrics.system.network.bytes_in)} | Out: ${formatBytes(metrics.system.network.bytes_out)}`}
              />
            </ListItem>
          </List>
        </MetricsCard>
      </Grid>

      {/* Storage Metrics */}
      <Grid item xs={12} md={6}>
        <MetricsCard title="Storage" icon={<StorageIcon />}>
          <List>
            <ListItem>
              <ListItemIcon>
                <StorageIcon />
              </ListItemIcon>
              <ListItemText
                primary="Storage Usage"
                secondary={`${metrics.storage.percent.toFixed(1)}% (${formatBytes(metrics.storage.used)} / ${formatBytes(metrics.storage.total)})`}
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <StorageIcon />
              </ListItemIcon>
              <ListItemText
                primary="Available Storage"
                secondary={formatBytes(metrics.storage.available)}
              />
            </ListItem>
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
