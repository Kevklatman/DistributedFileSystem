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
  ListItemIcon,
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
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [currentUpload, setCurrentUpload] = useState(null);
  const [uploadParts, setUploadParts] = useState([]);
  const fileInputRef = React.createRef(null);
  const [versionHistoryOpen, setVersionHistoryOpen] = useState(false);
  const [selectedFileVersions, setSelectedFileVersions] = useState([]);

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

  const initiateMultipartUpload = async (file, bucketName) => {
    try {
      const response = await axios.post(`${API_URL}/${bucketName}/${file.name}?uploads`);
      const uploadId = response.data.UploadId;
      setCurrentUpload({ file, uploadId, bucketName });
      return uploadId;
    } catch (error) {
      console.error('Error initiating multipart upload:', error);
      throw error;
    }
  };

  const uploadPart = async (part, partNumber, uploadId, bucketName, key) => {
    try {
      const response = await axios.put(
        `${API_URL}/${bucketName}/${key}?partNumber=${partNumber}&uploadId=${uploadId}`,
        part,
        {
          headers: {
            'Content-Type': 'application/octet-stream',
          },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            console.log(`Part ${partNumber} progress: ${percentCompleted}%`);
          },
        }
      );
      return {
        PartNumber: partNumber,
        ETag: response.headers.etag,
      };
    } catch (error) {
      console.error(`Error uploading part ${partNumber}:`, error);
      throw error;
    }
  };

  const completeMultipartUpload = async (uploadId, parts, bucketName, key) => {
    try {
      await axios.post(`${API_URL}/${bucketName}/${key}?uploadId=${uploadId}`, {
        Parts: parts,
      });
      setCurrentUpload(null);
      setUploadParts([]);
      fetchFiles();
    } catch (error) {
      console.error('Error completing multipart upload:', error);
      throw error;
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file || !selectedBucket) return;

    try {
      setUploadProgress(0);
      if (file.size > CHUNK_SIZE) {
        // Use multipart upload for large files
        const uploadId = await initiateMultipartUpload(file, selectedBucket);
        const parts = [];
        const totalParts = Math.ceil(file.size / CHUNK_SIZE);

        for (let partNumber = 1; partNumber <= totalParts; partNumber++) {
          const start = (partNumber - 1) * CHUNK_SIZE;
          const end = Math.min(start + CHUNK_SIZE, file.size);
          const chunk = file.slice(start, end);

          const part = await uploadPart(chunk, partNumber, uploadId, selectedBucket, file.name);
          parts.push(part);
          setUploadProgress((partNumber / totalParts) * 100);
          setUploadParts([...parts]);
        }

        await completeMultipartUpload(uploadId, parts, selectedBucket, file.name);
      } else {
        // Regular upload for small files
        const formData = new FormData();
        formData.append('file', file);
        await axios.put(`${API_URL}/${selectedBucket}/${file.name}`, file, {
          headers: { 'Content-Type': 'application/octet-stream' },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadProgress(percentCompleted);
          },
        });
      }

      setSnackbar({
        open: true,
        message: 'File uploaded successfully',
        severity: 'success'
      });
      fetchFiles();
    } catch (error) {
      console.error('Upload error:', error);
      setSnackbar({
        open: true,
        message: error.response?.data?.error || 'Failed to upload file',
        severity: 'error'
      });
    } finally {
      setUploadProgress(0);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDownloadFile = async (fileName, versionId = null) => {
    try {
      const url = versionId
        ? `${API_URL}/${selectedBucket}/${fileName}?versionId=${versionId}`
        : `${API_URL}/${selectedBucket}/${fileName}`;

      const response = await axios.get(url, {
        responseType: 'blob'
      });

      // Create a download link
      const downloadUrl = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);

      setSnackbar({
        open: true,
        message: 'File downloaded successfully',
        severity: 'success'
      });
    } catch (error) {
      console.error('Download error:', error);
      setSnackbar({
        open: true,
        message: error.response?.data?.error || 'Failed to download file',
        severity: 'error'
      });
    }
  };

  const handleDeleteFile = async (fileName, versionId = null) => {
    if (!window.confirm(`Are you sure you want to delete ${fileName}${versionId ? ' (version ' + versionId + ')' : ''}?`)) {
      return;
    }

    try {
      const url = versionId
        ? `${API_URL}/${selectedBucket}/${fileName}?versionId=${versionId}`
        : `${API_URL}/${selectedBucket}/${fileName}`;

      console.log('Attempting to delete file:', {
        url,
        bucket: selectedBucket,
        fileName,
        versionId
      });

      const response = await axios.delete(url, {
        headers: {
          'Accept': 'application/xml, text/xml, */*'
        }
      });

      console.log('Delete response:', response);
      fetchFiles();
      setSnackbar({
        open: true,
        message: 'File deleted successfully',
        severity: 'success'
      });
    } catch (error) {
      console.error('Delete error details:', {
        error,
        response: error.response,
        request: error.request,
        config: error.config
      });
      setSnackbar({
        open: true,
        message: error.response?.data?.error || 'Failed to delete file',
        severity: 'error'
      });
    }
  };

  const fetchVersionHistory = async (fileName) => {
    try {
      const response = await axios.get(`${API_URL}/${selectedBucket}/${fileName}?versions`);
      let versions = [];

      if (typeof response.data === 'string' && response.data.includes('<?xml')) {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(response.data, "text/xml");
        const versionElements = xmlDoc.getElementsByTagName('Version');

        versions = Array.from(versionElements).map(version => ({
          versionId: version.getElementsByTagName('VersionId')[0]?.textContent || '',
          lastModified: version.getElementsByTagName('LastModified')[0]?.textContent || '',
          size: parseInt(version.getElementsByTagName('Size')[0]?.textContent || '0'),
          isLatest: version.getElementsByTagName('IsLatest')[0]?.textContent === 'true'
        }));
      } else if (response.data.versions) {
        versions = response.data.versions;
      }

      setSelectedFileVersions(versions);
      setVersionHistoryOpen(true);
    } catch (error) {
      console.error('Error fetching version history:', error);
      setSnackbar({
        open: true,
        message: error.response?.data?.error || 'Failed to fetch version history',
        severity: 'error'
      });
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
        fetchVersionHistory(selectedFileMenu?.key);
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

  const toggleVersioning = async () => {
    if (!selectedBucket) return;
    try {
      await axios.put(`${API_URL}/${selectedBucket}/versioning`, {
        VersioningEnabled: !versioningEnabled
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
            VersioningEnabled: !versioningEnabled
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
          message: `Failed to toggle versioning: ${error.response?.data?.error || error.message}`,
          severity: 'error'
        });
      }
    }
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
                  key={bucket.Name}
                  secondaryAction={
                    <IconButton
                      edge="end"
                      aria-label="delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteBucket(bucket.Name);
                      }}
                    >
                      <Delete />
                    </IconButton>
                  }
                >
                  <ListItemText
                    primary={bucket.Name}
                    sx={{
                      cursor: 'pointer',
                      bgcolor: selectedBucket === bucket.Name ? 'action.selected' : 'transparent',
                      borderRadius: 1,
                      p: 1
                    }}
                    onClick={() => handleBucketSelect(bucket.Name)}
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
                      ref={fileInputRef}
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
        open={versionHistoryOpen}
        onClose={() => setVersionHistoryOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Version History</DialogTitle>
        <DialogContent>
          <List>
            {selectedFileVersions.map((version) => (
              <ListItem
                key={version.versionId}
                secondaryAction={
                  <Box>
                    <IconButton onClick={() => handleDownloadFile(selectedFileMenu?.key, version.versionId)}>
                      <Download />
                    </IconButton>
                    <IconButton onClick={() => handleDeleteFile(selectedFileMenu?.key, version.versionId)}>
                      <Delete />
                    </IconButton>
                  </Box>
                }
              >
                <ListItemText
                  primary={`Version: ${version.versionId}`}
                  secondary={`Last Modified: ${new Date(version.lastModified).toLocaleString()} | Size: ${version.size} bytes${version.isLatest ? ' (Latest)' : ''}`}
                />
              </ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setVersionHistoryOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* File Menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleFileMenuClose}
      >
        <MenuItem onClick={() => handleMenuItemClick('download')}>
          <ListItemIcon>
            <Download fontSize="small" />
          </ListItemIcon>
          <ListItemText>Download</ListItemText>
        </MenuItem>
        {versioningEnabled && (
          <MenuItem onClick={() => handleMenuItemClick('version-history')}>
            <ListItemIcon>
              <History fontSize="small" />
            </ListItemIcon>
            <ListItemText>Version History</ListItemText>
          </MenuItem>
        )}
        <MenuItem onClick={() => handleMenuItemClick('delete')}>
          <ListItemIcon>
            <Delete fontSize="small" />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
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
