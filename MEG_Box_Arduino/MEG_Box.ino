// MEG_Box
// 
// Original author:   William Gross
// 
//    v1:   4/1/2022
//        Written to solve the issues with sending tags and recieving inputs from
//        the MEG scanner at MCW. This program was meant to run on an Arduino that
//        interfaces through USB from the presentation computer to the MEG interface box


#define MP_STARTCODE    'x'
#define MP_GETTIME      't'   // ()  returns time
#define MP_ADDTIME      'a'   // (int ms)  adds ms to current millis
#define MP_OUTON        'o'   // (int n)   turns output n on
#define MP_OUTOFF       'l'   // (int n)   turns output n off
#define MP_OUTPULSE     'p'   // (int n)   perform a on/off pulse
#define MP_READRESPS    'r'   // See below:
#define MP_RESP_PSTART  '['
#define MP_RESP_PEND    ']'
#define MP_RESP_START   '<'
#define MP_RESP_END     '>'
#define MP_NUMRESP      'X'
    // Protocol for sending responses:
    // First, send: MP_NUMRESP, followed by the number of buttons (byte) with responses (if 0, end there).
    // Then, send the following sequence for each button:
      // MP_RESP_PSTART
      // byte b            button code (0, 1, ...)
      // byte n            number of responses (>0)
      // loop for n times:
      //    MP_RESP_START
      //    long t        ms time of response
      //    MP_RESP_END
      // MP_RESP_PEND 

#define   PULSE_WIDTH   100   // ms

#define NUM_OUT   5
#define NUM_IN    2

const unsigned char out_pins[NUM_OUT] = {4, 5, 6, 7, 8};
const unsigned char inout_pins[NUM_IN] = {9,10};
const unsigned char in_pins[NUM_IN] = {2, 3};

// Keep track of times for pulse generation
unsigned long out_pulse[NUM_OUT] = {0, 0, 0, 0, 0};
volatile unsigned long inout_pulse[NUM_IN] = {0, 0};

unsigned long millis_offset = 0;

// We will buffer this many responses while we wait for them to be read by the computer. If more responses are
// recieved they will overwrite (oldest will disappear first)
#define BUFFER_SIZE   100
// If we recieve the same button press within this number of ms, skip it
#define BOUNCE_SKIP   10

// resp_i[b] stores the current index of resp_times[b]. As the responses are read, this will increase
// and then "rotate" around resp_times. It's more efficient to rotate the starting value (versus always 
// using "0") and trying to shift the array in memory (which is very expensive)
unsigned int resp_i[NUM_IN] = {0,0};
// resp_last contains the index after the last recieved value. If resp_i[b] == resp_last[b], no new responses
// have been received
volatile unsigned int resp_last[NUM_IN] = {0,0};
// The ms times of recieved responses
volatile unsigned long resp_times_0[BUFFER_SIZE];
volatile unsigned long resp_times_1[BUFFER_SIZE];
volatile unsigned long last_time[NUM_IN] = {0,0};
unsigned long *resp_times[NUM_IN];

//////// INTERRUPT FUNCTIONS /////////
// To maintain precise timing, the responses are recorded by interrupt functions. No matter where the program is,
// when a button is pressed the microprocessor will interrupt processing and run the following codes to record button
// presses and timing. Because this is an interrupt, it needs to be kept simple.
void button_0_ISR() {
  unsigned long new_time = millis() - millis_offset;
  if((new_time - last_time[0]) < BOUNCE_SKIP) {
    return;
  }
  resp_times_0[resp_last[0]] = new_time;
  last_time[0] = new_time;

  inout_pulse[0] = 1;
  resp_last[0] += 1;
  if(resp_last[0] >= BUFFER_SIZE) {
    // We've gone over our limit, so loop back to 0 and keep going
    resp_last[0] = 0;
  }
}

// I know it's inefficient to hard code these, but I'm more concerned about timing
void button_1_ISR() {
  unsigned long new_time = millis() - millis_offset;
  if((new_time - last_time[1]) < BOUNCE_SKIP) {
    return;
  }
  resp_times_1[resp_last[1]] = new_time;
  last_time[1] = new_time;

  inout_pulse[1] = 1;
  resp_last[1] += 1;
  if(resp_last[1] >= BUFFER_SIZE) {
    // We've gone over our limit, so loop back to 0 and keep going
    resp_last[1] = 0;
  }
}


void send_resps() {
  byte n;
  // See above for the explanation of the protocol

  // Make local copies to avoid being interrupted/updated in the middle of sending
  unsigned int local_resp_last[NUM_IN];
  for(n=0;n<NUM_IN;n++) {
    local_resp_last[n] = resp_last[n];
  }

  byte num_resp = 0;
  
  for(n=0;n<NUM_IN;n++) {
    if(resp_i[n] != local_resp_last[n]) {
      num_resp++;
    }
  }
  Serial.write(MP_NUMRESP);
  Serial.write(num_resp);

  for(byte n=0;n<NUM_IN;n++) {
    if(resp_i[n] != local_resp_last[n]) {
      Serial.write(MP_RESP_PSTART);
      Serial.write(n);
      // Number of responses to send:
      if(local_resp_last[n]>resp_i[n]) {
        // the easy way
        Serial.write(local_resp_last[n] - resp_i[n]);
      }
      else {
        // we're crossing the loop-around point
        // e.g., 98 -> 2
        // [98,99,0,1]
        // (100 - 98) + 2 = 4
        Serial.write(BUFFER_SIZE-resp_i[n] + local_resp_last[n]);
      }

      // Responses:
      while(resp_i[n] != local_resp_last[n]) {
        Serial.write(MP_RESP_START);
        send_long(resp_times[n][resp_i[n]]);
        Serial.write(MP_RESP_END);

        resp_i[n]++;
        if(resp_i[n] >= BUFFER_SIZE) {
          resp_i[n] = 0;
        }
      }
      Serial.write(MP_RESP_PEND);
    }
  }
}

void setup() {
  byte i;
  
  Serial.begin(115200);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN,1);

  for(i=0;i<NUM_OUT;i++) {
    pinMode(out_pins[i],OUTPUT);
  }

  resp_times[0] = resp_times_0;
  resp_times[1] = resp_times_1;
  for(i=0;i<NUM_IN;i++) {
    //resp_times[i] = (unsigned long *)malloc(sizeof(unsigned long)*BUFFER_SIZE);
    pinMode(in_pins[i],INPUT);
    pinMode(inout_pins[i],OUTPUT);
  }

  // Attach the interrupt functions to the rising edge of the input pins
  attachInterrupt(digitalPinToInterrupt(in_pins[0]),button_0_ISR,RISING);
  
  attachInterrupt(digitalPinToInterrupt(in_pins[1]),button_1_ISR,RISING);
}

#define TIMEOUT   10000

size_t send_long(unsigned long data) {
  byte buf[4];
  buf[0] = data & 255;
  buf[1] = (data >> 8)  & 255;
  buf[2] = (data >> 16) & 255;
  buf[3] = (data >> 24) & 255;

  return Serial.write(buf, sizeof(buf));
}

bool waiting_command = false;
bool waiting_argument = false;
int command = 0;
unsigned long last_contact = 0;

void loop() {
  // Loop is designed to do everything asynch to avoid blocking. It waits for inputs, then sets flags
  // and keeps looping.
  byte b;
  
  if(Serial.available()>0) {
    // Keep track of when the last input was. If there's a gap, just start over (to avoid getting stuck in the middle of 
    // a command string when there's a dropped byte/
    last_contact = millis();

    b = Serial.read();
    if(waiting_command) {
      // We have currently recieved the "start" character and are waiting for the command
      switch(b) {
        case MP_GETTIME:
          // Just send the current clock time, and finish
          send_long(millis() - millis_offset);
          waiting_command = false;
          break;
        /*case MP_ADDTIME:
          // Add this amount to clock time. Not super useful.
          double x = s.substring(2).toDouble();
          millis_offset += x; */
        case MP_READRESPS:
          send_resps();
          waiting_command = false;
          break;
        case MP_OUTON:
          // Turn a single pin on. Sets the flag to wait for an argument before we do anything
          command = MP_OUTON;
          waiting_command = false;
          waiting_argument = true;
          break;
        case MP_OUTOFF:
          // Turn a pin off. Need to wait for the argument (the pin)
          command = MP_OUTOFF;
          waiting_command = false;
          waiting_argument = true;
          break;            
        case MP_OUTPULSE:
          // Turn a pin on and off for PULSE_WIDTH. Need to wait for the argument (the pin)
          command = MP_OUTPULSE;
          waiting_command = false;
          waiting_argument = true;
          break;            
        default:
          // Invalid command. Just reset.
          waiting_command = false;
          waiting_argument = false;        
          break;
      }
    }
    else if(waiting_argument) {
      // We've already recieved a command, but it needs an argument
      switch(command) {
        case MP_OUTON:
          // Finish writing ON to the pin `b`
          digitalWrite(out_pins[b],1);
          waiting_argument = false;
          break;
        case MP_OUTOFF:
          // Finish writing OFF to pin `b`
          digitalWrite(out_pins[b],0);
          waiting_argument = false;
          break;
        case MP_OUTPULSE:
          // Turn pulse on and set duration
          digitalWrite(out_pins[b],1);
          out_pulse[b] = millis() + PULSE_WIDTH;
          waiting_argument = false;
          break;
        default:
          // Invalid command stored. Just reset.
          waiting_command = false;
          waiting_argument = false;        
          break;
      }
    }
    else if(b==MP_STARTCODE) {
      // We're currently outside of all commands, and just recieved the start code. Now 
      // wait for the command
      waiting_command = true;
    }
  }

  
  // Turn pulse's off if the time has passed
  for(b=0;b<NUM_OUT;b++) {
    if(out_pulse[b] != 0 && out_pulse[b]<millis()) {
      digitalWrite(out_pins[b],0);
      out_pulse[b] = 0;
    }
  }
  for(b=0;b<NUM_IN;b++) {
    if(inout_pulse[b] != 0) {
      if(inout_pulse[b] == 1) {
        digitalWrite(inout_pins[b],1);
        inout_pulse[b] = millis() + PULSE_WIDTH;
      }
      else if(inout_pulse[b]<millis()) {
        digitalWrite(inout_pins[b],0);
        inout_pulse[b] = 0;
      }
    }
  }

  if(millis() - last_contact > TIMEOUT) {
    waiting_command = false;
    waiting_argument = false;
  }
}
