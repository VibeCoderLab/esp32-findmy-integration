#include <Arduino.h>
#include <Preferences.h>
#include <esp_bt.h>
#include <esp_bt_main.h>
#include <esp_gap_ble_api.h>
#include <esp_system.h>
#include <mbedtls/ecp.h>
#include <mbedtls/bignum.h>
#include <mbedtls/sha256.h>
#include "device_secrets.h"

// Keep Arduino from releasing controller memory before setup() when using IDF directly.
extern "C" bool btInUse() { return true; }

static Preferences prefs;
static struct { uint32_t index; uint8_t seed[32]; } state;
static uint32_t last_rotation;
static volatile bool advertising=false;
static uint8_t public_x[28];
static uint8_t payload[31]={0x1e,0xff,0x4c,0x00,0x12,0x19,0x00};
static esp_ble_adv_params_t params;

static int rng(void*,unsigned char* out,size_t len) {
  while(len) { uint32_t r=esp_random(); size_t n=len>4?4:len; memcpy(out,&r,n);out+=n;len-=n; }
  return 0;
}
static void kdf(const uint8_t* key,size_t n,const char* label,uint8_t* out,size_t length) {
  uint32_t counter=1;
  while(length) {
    uint8_t digest[32],be[4]={(uint8_t)(counter>>24),(uint8_t)(counter>>16),(uint8_t)(counter>>8),(uint8_t)counter};
    mbedtls_sha256_context ctx;mbedtls_sha256_init(&ctx);mbedtls_sha256_starts_ret(&ctx,0);
    mbedtls_sha256_update_ret(&ctx,key,n);mbedtls_sha256_update_ret(&ctx,be,4);
    mbedtls_sha256_update_ret(&ctx,(const uint8_t*)label,strlen(label));mbedtls_sha256_finish_ret(&ctx,digest);mbedtls_sha256_free(&ctx);
    size_t take=length>32?32:length;memcpy(out,digest,take);out+=take;length-=take;counter++;
  }
}
static bool derive_public() {
  uint8_t at[72];kdf(state.seed,32,"diversify",at,72);
  mbedtls_ecp_group group;mbedtls_ecp_group_init(&group);
  mbedtls_ecp_point point;mbedtls_ecp_point_init(&point);
  mbedtls_mpi u,v,d,nminus,p;mbedtls_mpi_init(&u);mbedtls_mpi_init(&v);mbedtls_mpi_init(&d);mbedtls_mpi_init(&nminus);mbedtls_mpi_init(&p);
  int rc=mbedtls_ecp_group_load(&group,MBEDTLS_ECP_DP_SECP224R1);
  if(!rc)rc=mbedtls_mpi_sub_int(&nminus,&group.N,1);
  if(!rc)rc=mbedtls_mpi_read_binary(&u,at,36);
  if(!rc)rc=mbedtls_mpi_mod_mpi(&u,&u,&nminus);
  if(!rc)rc=mbedtls_mpi_add_int(&u,&u,1);
  if(!rc)rc=mbedtls_mpi_read_binary(&v,at+36,36);
  if(!rc)rc=mbedtls_mpi_mod_mpi(&v,&v,&nminus);
  if(!rc)rc=mbedtls_mpi_add_int(&v,&v,1);
  if(!rc)rc=mbedtls_mpi_read_binary(&d,MASTER_KEY,28);
  if(!rc)rc=mbedtls_mpi_mul_mpi(&p,&u,&d);
  if(!rc)rc=mbedtls_mpi_add_mpi(&p,&p,&v);
  if(!rc)rc=mbedtls_mpi_mod_mpi(&p,&p,&group.N);
  if(!rc)rc=mbedtls_ecp_mul(&group,&point,&p,&group.G,rng,nullptr);
  if(!rc)rc=mbedtls_mpi_write_binary(&point.X,public_x,28);
  mbedtls_mpi_free(&u);mbedtls_mpi_free(&v);mbedtls_mpi_free(&d);mbedtls_mpi_free(&nminus);mbedtls_mpi_free(&p);
  mbedtls_ecp_point_free(&point);mbedtls_ecp_group_free(&group);
  memset(at,0,sizeof(at));
  if(rc) Serial.printf("KEY_DERIVATION_ERROR=%d\n",rc);
  return rc==0;
}
static void status() {
  uint8_t digest[32];mbedtls_sha256_ret(public_x,28,digest,0);
  Serial.printf("BEACON index=%lu hash=",(unsigned long)state.index);
  for(int i=0;i<8;i++)Serial.printf("%02x",digest[i]);
  Serial.printf(" advertising=%d interval_ms=1000 rotation_seconds=900\n",advertising?1:0);
}
static void next_check() {
  uint8_t saved_seed[32],saved_x[28],next[32];
  memcpy(saved_seed,state.seed,32);memcpy(saved_x,public_x,28);
  kdf(state.seed,32,"update",next,32);memcpy(state.seed,next,32);state.index++;
  Serial.print("NEXT_CHECK ");if(derive_public())status();
  state.index--;memcpy(state.seed,saved_seed,32);memcpy(public_x,saved_x,28);
  memset(saved_seed,0,32);memset(next,0,32);
}
static void callback(esp_gap_ble_cb_event_t event,esp_ble_gap_cb_param_t* p) {
  if(event==ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT) {
    if(p->adv_data_raw_cmpl.status==ESP_BT_STATUS_SUCCESS) esp_ble_gap_start_advertising(&params);
    else Serial.println("ADV_CONFIG_ERROR");
  }
  if(event==ESP_GAP_BLE_ADV_START_COMPLETE_EVT) {
    advertising=p->adv_start_cmpl.status==ESP_BT_STATUS_SUCCESS;
    if(!advertising)Serial.println("ADV_START_ERROR");
  }
  if(event==ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT)advertising=false;
}
static bool publish() {
  if(advertising){esp_ble_gap_stop_advertising();delay(150);}
  if(!derive_public())return false;
  uint8_t addr[6];memcpy(addr,public_x,6);addr[0]|=0xc0;
  memcpy(payload+7,public_x+6,22);payload[29]=public_x[0]>>6;payload[30]=0;
  if(esp_ble_gap_set_rand_addr(addr)!=ESP_OK)return false;
  if(esp_ble_gap_config_adv_data_raw(payload,sizeof(payload))!=ESP_OK)return false;
  delay(150);status();return true;
}
static void fatal(const char* message) {
  Serial.println(message);while(true)delay(1000);
}
void setup() {
  Serial.begin(115200);delay(200);
  if(!prefs.begin("esp32lab",false))fatal("NVS_OPEN_ERROR");
  if(prefs.getUInt("identity",0)==IDENTITY_ID && prefs.getBytesLength("state")==sizeof(state)) {
    prefs.getBytes("state",&state,sizeof(state));
  } else {
    state.index=INITIAL_INDEX;memcpy(state.seed,INITIAL_SEED,32);
    if(prefs.putBytes("state",&state,sizeof(state))!=sizeof(state))fatal("NVS_WRITE_ERROR");
    if(prefs.putUInt("identity",IDENTITY_ID)!=sizeof(uint32_t))fatal("NVS_ID_ERROR");
  }
  esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
  esp_bt_controller_config_t config=BT_CONTROLLER_INIT_CONFIG_DEFAULT();
  config.mode=ESP_BT_MODE_BLE;
  esp_err_t init_result=esp_bt_controller_init(&config);
  if(init_result!=ESP_OK){Serial.printf("BT_INIT_CODE=%d\n",init_result);fatal("BT_INIT_ERROR");}
  if(esp_bt_controller_enable(ESP_BT_MODE_BLE)!=ESP_OK)fatal("BT_ENABLE_ERROR");
  if(esp_bluedroid_init()!=ESP_OK)fatal("BLE_INIT_ERROR");
  if(esp_bluedroid_enable()!=ESP_OK)fatal("BLE_ENABLE_ERROR");
  esp_ble_gap_register_callback(callback);
  esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV,ESP_PWR_LVL_P3);
  memset(&params,0,sizeof(params));params.adv_int_min=0x0640;params.adv_int_max=0x0640;
  params.adv_type=ADV_TYPE_NONCONN_IND;params.own_addr_type=BLE_ADDR_TYPE_RANDOM;
  params.channel_map=ADV_CHNL_ALL;params.adv_filter_policy=ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY;
  if(!publish())fatal("PUBLISH_ERROR");
  last_rotation=millis();
}
void loop() {
  static String command;
  while(Serial.available()) {
    char c=Serial.read();
    if(c=='\n') { command.trim();if(command=="STATUS")status();if(command=="NEXTCHECK")next_check();command=""; }
    else if(command.length()<32)command+=c;
  }
  if((uint32_t)(millis()-last_rotation)>=900000UL) {
    uint8_t next[32];kdf(state.seed,32,"update",next,32);memcpy(state.seed,next,32);memset(next,0,32);state.index++;
    if(prefs.putBytes("state",&state,sizeof(state))!=sizeof(state))fatal("NVS_WRITE_ERROR");
    if(!publish())fatal("PUBLISH_ERROR");last_rotation=millis();
  }
  delay(50);
}
