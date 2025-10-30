const video = document.getElementById('video');
const startBtn = document.getElementById('start');
const statusDiv = document.getElementById('status');

startBtn.addEventListener('click', async () => {
  const station = document.getElementById('station').value;
  const stream = await navigator.mediaDevices.getUserMedia({video:true});
  video.srcObject = stream;
  setInterval(async ()=>{
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video,0,0,canvas.width,canvas.height);
    const data = canvas.toDataURL('image/jpeg');
    statusDiv.innerText = 'Checking...';
    try{
      const res = await fetch('/api/checkin',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body: JSON.stringify({image_b64:data, station:station})
      });
      const j = await res.json();
      if(j.success){
        statusDiv.innerText = 'PASS: user '+j.user_id+' ticket '+j.ticket_id;
      } else {
        statusDiv.innerText = 'DENY: '+ (j.reason || 'no_match');
      }
    }catch(e){
      statusDiv.innerText = 'Error: '+e;
    }
  }, 2000);
});
