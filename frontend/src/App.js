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

  useEffect(() => {
    fetchBuckets();
  }, []);

  useEffect(() => {
    if (selectedBucket) {
      fetchFiles(selectedBucket);
      fetchVersioningStatus(selectedBucket);
    }
  }, [selectedBucket]);

  const fetchBuckets = async () => {
    try {
      const response = await axios.get(`${API_URL}/`, {
        headers: { Accept: 'application/json' }
      });
      setBuckets(response.data.buckets || []);
    } catch (error) {
      console.error('Error fetching buckets:', error);
    }
  };

  const handleCreateBucket = async () => {
    if (!newBucketName) {
      alert('Please enter a bucket name');
      return;
    }

    try {
      await axios.put(`${API_URL}/${newBucketName}`, null, {
        headers: { 'Content-Type': 'application/xml' }
      });
      setCreateBucketOpen(false);
      setNewBucketName('');
      fetchBuckets();
    } catch (error) {
      if (error.response?.data) {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(error.response.data, "text/xml");
        const errorMessage = xmlDoc.querySelector("Message")?.textContent;
        alert(errorMessage || 'Failed to create bucket');
      } else {
        alert('Failed to create bucket');
      }
    }
  };

  const handleFileUpload = async (event) => {
    if (!selectedBucket) return;

    const file = event.target.files[0];
    if (!file) return;

    // Use multipart upload for files larger than 5MB
    if (file.size > CHUNK_SIZE) {
      await handleMultipartUpload(file);
    } else {
      await handleSimpleUpload(file);
    }
  };

  const handleSimpleUpload = async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      await axios.put(`${API_URL}/${selectedBucket}/${file.name}`, formData);
      fetchFiles(selectedBucket);
    } catch (error) {
      console.error('Error uploading file:', error);
      alert('Failed to upload file');
    }
  };

  const handleMultipartUpload = async (file) => {
    try {
      // Initialize multipart upload
      const initResponse = await axios.post(`${API_URL}/${selectedBucket}/${file.name}?uploads`);
      const uploadId = initResponse.data.UploadId;

      // Split file into chunks and upload parts
      const chunks = Math.ceil(file.size / CHUNK_SIZE);
      const parts = [];

      for (let i = 0; i < chunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunk = file.slice(start, end);

        const partResponse = await axios.put(
          `${API_URL}/${selectedBucket}/${file.name}?partNumber=${i + 1}&uploadId=${uploadId}`,
          chunk
        );

        parts.push({
          PartNumber: i + 1,
          ETag: partResponse.headers.etag
        });

        setUploadProgress(Math.round((i + 1) * 100 / chunks));
      }

      // Complete multipart upload
      await axios.post(
        `${API_URL}/${selectedBucket}/${file.name}?uploadId=${uploadId}`,
        { parts }
      );

      setUploadProgress(0);
      fetchFiles(selectedBucket);
    } catch (error) {
      console.error('Error in multipart upload:', error);
      alert('Failed to upload file');
      setUploadProgress(0);
    }
  };

  const fetchFiles = async (bucketName) => {
    try {
      const response = await axios.get(`${API_URL}/${bucketName}`);
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(response.data, "text/xml");
      const objects = Array.from(xmlDoc.querySelectorAll("Contents")).map(obj => ({
        key: obj.querySelector("Key").textContent,
        lastModified: obj.querySelector("LastModified").textContent,
        size: parseInt(obj.querySelector("Size").textContent),
      }));
      setFiles(objects);
    } catch (error) {
      console.error('Error fetching files:', error);
    }
  };

  const fetchVersioningStatus = async (bucketName) => {
    try {
      const response = await axios.get(`${API_URL}/${bucketName}?versioning`);
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(response.data, "text/xml");
      const status = xmlDoc.querySelector("Status")?.textContent;
      setVersioningEnabled(status === "Enabled");
    } catch (error) {
      console.error('Error fetching versioning status:', error);
    }
  };

  const toggleVersioning = async () => {
    try {
      const status = versioningEnabled ? "Suspended" : "Enabled";
      await axios.put(`${API_URL}/${selectedBucket}?versioning`, {
        VersioningConfiguration: { Status: status }
      });
      setVersioningEnabled(!versioningEnabled);
    } catch (error) {
      console.error('Error toggling versioning:', error);
    }
  };

  const fetchVersions = async (fileName) => {
    try {
      const response = await axios.get(`${API_URL}/${selectedBucket}?versions`);
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(response.data, "text/xml");
      const versions = Array.from(xmlDoc.querySelectorAll("Version")).map(ver => ({
        versionId: ver.querySelector("VersionId").textContent,
        lastModified: ver.querySelector("LastModified").textContent,
        size: parseInt(ver.querySelector("Size").textContent),
      }));
      setVersions(versions.filter(v => v.key === fileName));
      setVersionDialogOpen(true);
    } catch (error) {
      console.error('Error fetching versions:', error);
    }
  };

  const handleDeleteFile = async (fileName) => {
    try {
      await axios.delete(`${API_URL}/${selectedBucket}/${fileName}`);
      fetchFiles(selectedBucket);
    } catch (error) {
      console.error('Error deleting file:', error);
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
    }
  };

  const handleFileMenuClick = (event, file) => {
    setMenuAnchorEl(event.currentTarget);
    setSelectedFileMenu(file);
  };

  const handleFileMenuClose = () => {
    setMenuAnchorEl(null);
    setSelectedFileMenu(null);
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
              <IconButton onClick={() => setCreateBucketOpen(true)}>
                <CreateNewFolder />
              </IconButton>
            </Box>
            <List>
              {buckets.map((bucket) => (
                <Button
                  key={bucket.name}
                  fullWidth
                  variant={selectedBucket === bucket.name ? "contained" : "text"}
                  onClick={() => setSelectedBucket(bucket.name)}
                  sx={{ justifyContent: "flex-start", mb: 1 }}
                >
                  {bucket.name}
                </Button>
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
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateBucketOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateBucket} variant="contained">Create</Button>
        </DialogActions>
      </Dialog>

      {/* Version History Dialog */}
      <Dialog open={versionDialogOpen} onClose={() => setVersionDialogOpen(false)}>
        <DialogTitle>Version History</DialogTitle>
        <DialogContent>
          <List>
            {versions.map((version) => (
              <ListItem key={version.versionId}>
                <ListItemText
                  primary={`Version: ${version.versionId}`}
                  secondary={`Modified: ${new Date(version.lastModified).toLocaleString()}`}
                />
                <IconButton onClick={() => handleDownloadFile(selectedFile.key, version.versionId)}>
                  <Download />
                </IconButton>
              </ListItem>
            ))}
          </List>
        </DialogContent>
      </Dialog>

      {/* File Menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleFileMenuClose}
      >
        <MenuItem onClick={() => {
          handleDownloadFile(selectedFileMenu?.key);
          handleFileMenuClose();
        }}>
          <Download sx={{ mr: 1 }} /> Download
        </MenuItem>
        {versioningEnabled && (
          <MenuItem onClick={() => {
            fetchVersions(selectedFileMenu?.key);
            handleFileMenuClose();
          }}>
            <History sx={{ mr: 1 }} /> Version History
          </MenuItem>
        )}
        <MenuItem onClick={() => {
          handleDeleteFile(selectedFileMenu?.key);
          handleFileMenuClose();
        }}>
          <Delete sx={{ mr: 1 }} /> Delete
        </MenuItem>
      </Menu>
    </Box>
  );
}

export default App;
