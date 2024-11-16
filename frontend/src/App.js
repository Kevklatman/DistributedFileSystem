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
} from '@mui/material';
import {
  CloudUpload,
  CreateNewFolder,
  Delete,
  History,
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

function App() {
  const [buckets, setBuckets] = useState([]);
  const [selectedBucket, setSelectedBucket] = useState(null);
  const [files, setFiles] = useState([]);
  const [createBucketOpen, setCreateBucketOpen] = useState(false);
  const [newBucketName, setNewBucketName] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);

  useEffect(() => {
    fetchBuckets();
  }, []);

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
      const response = await axios.put(`${API_URL}/${newBucketName}`, null, {
        headers: {
          'Content-Type': 'application/xml'
        }
      });
      setCreateBucketOpen(false);
      setNewBucketName('');
      fetchBuckets();
    } catch (error) {
      console.error('Error creating bucket:', error);
      // Parse XML error message if available
      if (error.response?.data) {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(error.response.data, "text/xml");
        const errorMessage = xmlDoc.querySelector("Message")?.textContent;
        alert(errorMessage || 'Failed to create bucket. Please ensure the bucket name follows S3 naming rules:\n- Between 3 and 63 characters\n- Lowercase letters, numbers, and hyphens only\n- Cannot start or end with hyphen');
      } else {
        alert('Failed to create bucket. Please try again.');
      }
    }
  };

  const handleFileUpload = async (event) => {
    if (!selectedBucket) return;

    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.put(`${API_URL}/${selectedBucket}/${file.name}`, formData);
      fetchFiles(selectedBucket);
    } catch (error) {
      console.error('Error uploading file:', error);
    }
  };

  const fetchFiles = async (bucketName) => {
    try {
      const response = await axios.get(`${API_URL}/${bucketName}`);
      setFiles(response.data.objects || []);
    } catch (error) {
      console.error('Error fetching files:', error);
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
                  onClick={() => {
                    setSelectedBucket(bucket.name);
                    fetchFiles(bucket.name);
                  }}
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
              )}
            </Box>
            <List>
              {files.map((file) => (
                <Box
                  key={file.key}
                  display="flex"
                  alignItems="center"
                  justifyContent="space-between"
                  p={1}
                  borderBottom="1px solid #eee"
                >
                  <Typography>{file.key}</Typography>
                  <Box>
                    <IconButton>
                      <History />
                    </IconButton>
                    <IconButton>
                      <Delete />
                    </IconButton>
                  </Box>
                </Box>
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
    </Box>
  );
}

export default App;
