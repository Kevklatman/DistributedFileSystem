import React, { useState, useEffect } from 'react';
import {
  Container,
  Box,
  Typography,
  AppBar,
  Toolbar,
  List,
  Paper,
  IconButton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel,
  CircularProgress,
  ListItem,
  ListItemText,
  ListItemSecondary,
  Menu,
  MenuItem,
  Snackbar
} from '@mui/material';
import {
  CloudUpload,
  CreateNewFolder,
  Delete,
  History,
  Download,
  MoreVert,
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = 'http://localhost:5555';
const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks for multipart upload

// Configure axios defaults
axios.defaults.headers.common['Accept'] = 'application/json';

const validateBucketName = (bucketName) => {
  if (!bucketName) return "Bucket name cannot be empty";
  if (bucketName.length < 3 || bucketName.length > 63)
    return "Bucket name must be between 3 and 63 characters";
  if (!/^[a-z0-9][a-z0-9.-]*[a-z0-9]$/.test(bucketName))
    return "Bucket name can only contain lowercase letters, numbers, dots (.), and hyphens (-)";
  if (/\.{2,}/.test(bucketName))
    return "Bucket name cannot contain consecutive dots";
  if (/^(?:\d+\.){3}\d+$/.test(bucketName))
    return "Bucket name cannot be formatted as an IP address";
  return null;
};

const createBucketIfNeeded = async (bucketName) => {
  const validationError = validateBucketName(bucketName);
  if (validationError) {
    throw new Error(validationError);
  }
  try {
    await axios.put(`${API_URL}/${bucketName}`);
    return true;
  } catch (error) {
    if (error.response?.data?.error) {
      throw new Error(error.response.data.error);
    }
    throw error;
  }
};

const parseXMLResponse = (xmlString) => {
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(xmlString, "text/xml");

  const contents = xmlDoc.getElementsByTagName('Contents');
  const objects = Array.from(contents).map(content => {
    return {
      key: content.getElementsByTagName('Key')[0]?.textContent || '',
      lastModified: content.getElementsByTagName('LastModified')[0]?.textContent || '',
      size: parseInt(content.getElementsByTagName('Size')[0]?.textContent || '0'),
      storageClass: content.getElementsByTagName('StorageClass')[0]?.textContent || ''
    };
  });

  return objects;
};

function App() {
  const [buckets, setBuckets] = useState([]);
  const [selectedBucket, setSelectedBucket] = useState(null);
  const [files, setFiles] = useState([]);
  const [createBucketOpen, setCreateBucketOpen] = useState(false);
  const [newBucketName, setNewBucketName] = useState('');
  const [versioningEnabled, setVersioningEnabled] = useState(false);
  const [versions, setVersions] = useState([]);
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [menuAnchorEl, setMenuAnchorEl] = useState(null);
  const [selectedFileMenu, setSelectedFileMenu] = useState(null);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'info'
  });

  useEffect(() => {
    fetchBuckets();
  }, []);

  useEffect(() => {
    console.log('Selected bucket changed to:', selectedBucket);
    if (selectedBucket) {
      fetchFiles();
      fetchVersioningStatus();
    } else {
      setFiles([]);
    }
  }, [selectedBucket]);

  const fetchBuckets = async () => {
    try {
      console.log('Fetching buckets...');
      const response = await axios.get(`${API_URL}/`);
      console.log('Buckets response:', response.data);
      if (response.data.buckets) {
        setBuckets(response.data.buckets);
      } else {
        console.error('Unexpected response format:', response.data);
        setBuckets([]);
      }
    } catch (error) {
      console.error('Error fetching buckets:', error.response || error);
      setBuckets([]);
    }
  };

  const fetchFiles = async () => {
    if (!selectedBucket) return;
    try {
      console.log(`Fetching files for bucket: ${selectedBucket}`);
      const response = await axios.get(`${API_URL}/${selectedBucket}`, {
        headers: {
          'Accept': 'application/xml, text/xml, */*'
        },
        transformResponse: [(data) => {
          // Keep the original response
          return data;
        }]
      });

      console.log('Files response:', response.data);

      // Check if response is XML
      if (typeof response.data === 'string' && response.data.includes('<?xml')) {
        const objects = parseXMLResponse(response.data);
        console.log('Parsed objects from XML:', objects);
        setFiles(objects);
      } else if (response.data.objects) {
        // Handle JSON response if server sends JSON
        console.log('Setting files from JSON:', response.data.objects);
        setFiles(response.data.objects);
      } else {
        console.warn('Unexpected response format:', response.data);
        setFiles([]);
      }
    } catch (error) {
      console.error('Error fetching files:', error.response?.data || error);
      setSnackbar({
        open: true,
        message: error.response?.data?.error || 'Failed to fetch files',
        severity: 'error'
      });
      setFiles([]);
    }
  };

  const fetchVersioningStatus = async () => {
    if (!selectedBucket) return;
    try {
      const response = await axios.get(`${API_URL}/${selectedBucket}/versioning`);
      setVersioningEnabled(response.data.Status === 'Enabled');
    } catch (error) {
      console.error('Error fetching versioning status:', error);
      // If bucket doesn't exist, try to create it
      if (error.response?.status === 400 && error.response?.data?.error === 'Bucket does not exist') {
        try {
          await createBucketIfNeeded(selectedBucket);
          // After creating bucket, fetch versioning status again
          const response = await axios.get(`${API_URL}/${selectedBucket}/versioning`);
          setVersioningEnabled(response.data.Status === 'Enabled');
          setSnackbar({
            open: true,
            message: 'Bucket created successfully',
            severity: 'success'
          });
        } catch (createError) {
          setSnackbar({
            open: true,
            message: `Failed to create bucket: ${createError.message}`,
            severity: 'error'
          });
        }
      } else {
        setSnackbar({
          open: true,
          message: error.response?.data?.error || 'Failed to fetch versioning status',
          severity: 'error'
        });
      }
    }
  };

  const handleCreateBucket = async () => {
    if (!newBucketName) {
      alert('Please enter a bucket name');
      return;
    }

    try {
      console.log(`Creating bucket: ${newBucketName}`);
      await createBucketIfNeeded(newBucketName);
      setCreateBucketOpen(false);
      setNewBucketName('');
      fetchBuckets();
    } catch (error) {
      console.error('Error creating bucket:', error.response?.data || error);
      alert(error.response?.data?.error || 'Failed to create bucket');
    }
  };

  const handleDeleteBucket = async (bucketName) => {
    if (!window.confirm(`Are you sure you want to delete bucket "${bucketName}"?`)) {
      return;
    }

    try {
      console.log(`Deleting bucket: ${bucketName}`);
      await axios.delete(`${API_URL}/${bucketName}`);
      if (selectedBucket === bucketName) {
        setSelectedBucket(null);
        setFiles([]);
      }
      fetchBuckets();
    } catch (error) {
      console.error('Error deleting bucket:', error.response?.data || error);
      alert(error.response?.data?.error || 'Failed to delete bucket');
    }
  };

  const handleFileUpload = async (event) => {
    const files = event.target.files;
    if (!files.length || !selectedBucket) return;

    const file = files[0];
    setUploadProgress(0);

    try {
      if (file.size > CHUNK_SIZE) {
        await handleMultipartUpload(file);
      } else {
        await handleSimpleUpload(file);
      }
      fetchFiles();
    } catch (error) {
      console.error('Error uploading file:', error);
      alert('Failed to upload file');
    } finally {
      setUploadProgress(0);
    }
  };

  const handleSimpleUpload = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    await axios.put(
      `${API_URL}/${selectedBucket}/${file.name}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    );
  };

  const handleMultipartUpload = async (file) => {
    // Initialize multipart upload
    console.log('Initializing multipart upload...');
    const initResponse = await axios.post(`${API_URL}/${selectedBucket}/${file.name}?uploads`);
    const uploadId = initResponse.data.UploadId;

    try {
      // Split file into chunks and upload parts
      const chunks = Math.ceil(file.size / CHUNK_SIZE);
      const parts = [];

      for (let i = 0; i < chunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunk = file.slice(start, end);

        console.log(`Uploading part ${i + 1}/${chunks}...`);
        const partResponse = await axios.put(
          `${API_URL}/${selectedBucket}/${file.name}?partNumber=${i + 1}&uploadId=${uploadId}`,
          chunk,
          {
            headers: {
              'Content-Type': 'application/octet-stream'
            }
          }
        );

        parts.push({
          PartNumber: i + 1,
          ETag: partResponse.headers.etag
        });

        setUploadProgress(Math.round((i + 1) * 100 / chunks));
      }

      // Complete multipart upload
      console.log('Completing multipart upload...');
      await axios.post(
        `${API_URL}/${selectedBucket}/${file.name}?uploadId=${uploadId}`,
        { parts }
      );
    } catch (error) {
      // Abort the multipart upload on error
      console.error('Error in multipart upload:', error);
      await axios.delete(
        `${API_URL}/${selectedBucket}/${file.name}?uploadId=${uploadId}`
      );
      throw error;
    }
  };

  const handleDownloadFile = async (fileName, versionId = null) => {
    try {
      const url = versionId
        ? `${API_URL}/${selectedBucket}/${fileName}?versionId=${versionId}`
        : `${API_URL}/${selectedBucket}/${fileName}`;

      const response = await axios.get(url, { responseType: 'blob' });
      const blob = new Blob([response.data]);
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      console.error('Error downloading file:', error);
      alert('Failed to download file');
    }
  };

  const handleDeleteFile = async (fileName) => {
    if (!window.confirm(`Are you sure you want to delete "${fileName}"?`)) {
      return;
    }

    try {
      await axios.delete(`${API_URL}/${selectedBucket}/${fileName}`);
      fetchFiles();
    } catch (error) {
      console.error('Error deleting file:', error);
      alert('Failed to delete file');
    }
  };

  const toggleVersioning = async () => {
    if (!selectedBucket) return;
    try {
      await axios.put(`${API_URL}/${selectedBucket}/versioning`, {
        Status: versioningEnabled ? 'Suspended' : 'Enabled'
      });
      setVersioningEnabled(!versioningEnabled);
      setSnackbar({
        open: true,
        message: `Versioning ${!versioningEnabled ? 'enabled' : 'disabled'} successfully`,
        severity: 'success'
      });
    } catch (error) {
      console.error('Error toggling versioning:', error);
      // If bucket doesn't exist, try to create it
      if (error.response?.status === 400 && error.response?.data?.error === 'Bucket does not exist') {
        try {
          await createBucketIfNeeded(selectedBucket);
          // After creating bucket, try toggling versioning again
          await axios.put(`${API_URL}/${selectedBucket}/versioning`, {
            Status: versioningEnabled ? 'Suspended' : 'Enabled'
          });
          setVersioningEnabled(!versioningEnabled);
          setSnackbar({
            open: true,
            message: `Bucket created and versioning ${!versioningEnabled ? 'enabled' : 'disabled'} successfully`,
            severity: 'success'
          });
        } catch (createError) {
          setSnackbar({
            open: true,
            message: `Failed to create bucket: ${createError.message}`,
            severity: 'error'
          });
        }
      } else {
        setSnackbar({
          open: true,
          message: error.response?.data?.error || 'Failed to toggle versioning',
          severity: 'error'
        });
      }
    }
  };

  const fetchVersions = async (fileName) => {
    try {
      const response = await axios.get(`${API_URL}/${selectedBucket}/${fileName}?versions`);
      const versions = response.data.Versions || [];
      setVersions(versions);
      setVersionDialogOpen(true);
    } catch (error) {
      console.error('Error fetching versions:', error);
      alert('Failed to fetch versions');
    }
  };

  const handleFileMenuClick = (event, file) => {
    event.preventDefault();
    setMenuAnchorEl(event.currentTarget);
    setSelectedFileMenu(file);
  };

  const handleFileMenuClose = () => {
    // Ensure we remove focus from menu items before closing
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    setMenuAnchorEl(null);
    setSelectedFileMenu(null);
  };

  const handleMenuItemClick = (action) => {
    // Execute the action
    switch (action) {
      case 'download':
        handleDownloadFile(selectedFileMenu?.key);
        break;
      case 'version-history':
        fetchVersions(selectedFileMenu?.key);
        break;
      case 'delete':
        handleDeleteFile(selectedFileMenu?.key);
        break;
    }
    // Close menu after action
    handleFileMenuClose();
  };

  const handleBucketSelect = (bucketName) => {
    console.log('Selecting bucket:', bucketName);
    setSelectedBucket(bucketName);
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Distributed File System
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Box display="flex" gap={2}>
          {/* Buckets Panel */}
          <Paper sx={{ width: 240, p: 2 }}>
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
              <Typography variant="h6">Buckets</Typography>
              <IconButton onClick={() => setCreateBucketOpen(true)} title="Create new bucket">
                <CreateNewFolder />
              </IconButton>
            </Box>
            <List>
              {buckets.map((bucket) => (
                <ListItem
                  key={bucket.name}
                  secondaryAction={
                    <IconButton
                      edge="end"
                      aria-label="delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteBucket(bucket.name);
                      }}
                    >
                      <Delete />
                    </IconButton>
                  }
                >
                  <ListItemText
                    primary={bucket.name}
                    sx={{
                      cursor: 'pointer',
                      bgcolor: selectedBucket === bucket.name ? 'action.selected' : 'transparent',
                      borderRadius: 1,
                      p: 1
                    }}
                    onClick={() => handleBucketSelect(bucket.name)}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>

          {/* Files Panel */}
          <Paper sx={{ flexGrow: 1, p: 2 }}>
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
              <Typography variant="h6">
                {selectedBucket ? `Files in ${selectedBucket}` : 'Select a bucket'}
              </Typography>
              {selectedBucket && (
                <Box display="flex" alignItems="center" gap={2}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={versioningEnabled}
                        onChange={toggleVersioning}
                        color="primary"
                      />
                    }
                    label="Versioning"
                  />
                  <Button
                    variant="contained"
                    startIcon={<CloudUpload />}
                    component="label"
                  >
                    Upload File
                    <input
                      type="file"
                      hidden
                      onChange={handleFileUpload}
                    />
                  </Button>
                </Box>
              )}
            </Box>

            {uploadProgress > 0 && (
              <Box display="flex" alignItems="center" gap={2} mb={2}>
                <CircularProgress variant="determinate" value={uploadProgress} />
                <Typography>Uploading: {uploadProgress}%</Typography>
              </Box>
            )}

            <List>
              {files.map((file) => (
                <ListItem
                  key={file.key}
                  secondaryAction={
                    <IconButton onClick={(e) => handleFileMenuClick(e, file)}>
                      <MoreVert />
                    </IconButton>
                  }
                >
                  <ListItemText
                    primary={file.key}
                    secondary={`Last modified: ${new Date(file.lastModified).toLocaleString()}`}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Box>
      </Container>

      {/* Create Bucket Dialog */}
      <Dialog open={createBucketOpen} onClose={() => setCreateBucketOpen(false)}>
        <DialogTitle>Create New Bucket</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Bucket Name"
            fullWidth
            value={newBucketName}
            onChange={(e) => setNewBucketName(e.target.value)}
            helperText="Bucket names must be between 3 and 63 characters long and can contain only lowercase letters, numbers, and hyphens"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateBucketOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateBucket} variant="contained">Create</Button>
        </DialogActions>
      </Dialog>

      {/* Version History Dialog */}
      <Dialog
        open={versionDialogOpen}
        onClose={() => setVersionDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Version History</DialogTitle>
        <DialogContent>
          <List>
            {versions.map((version) => (
              <ListItem
                key={version.versionId}
                secondaryAction={
                  <IconButton onClick={() => handleDownloadFile(selectedFile?.key, version.versionId)}>
                    <Download />
                  </IconButton>
                }
              >
                <ListItemText
                  primary={`Version: ${version.versionId}`}
                  secondary={`Modified: ${new Date(version.lastModified).toLocaleString()}`}
                />
              </ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setVersionDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* File Menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleFileMenuClose}
        MenuListProps={{
          'aria-label': 'File actions',
          autoFocusItem: false
        }}
      >
        <MenuItem
          key="download"
          onClick={() => handleMenuItemClick('download')}
        >
          <Download sx={{ mr: 1 }} /> Download
        </MenuItem>
        {versioningEnabled && (
          <MenuItem
            key="version-history"
            onClick={() => handleMenuItemClick('version-history')}
          >
            <History sx={{ mr: 1 }} /> Version History
          </MenuItem>
        )}
        <MenuItem
          key="delete"
          onClick={() => handleMenuItemClick('delete')}
        >
          <Delete sx={{ mr: 1 }} /> Delete
        </MenuItem>
      </Menu>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        message={snackbar.message}
        severity={snackbar.severity}
      />
    </Box>
  );
}

export default App;
