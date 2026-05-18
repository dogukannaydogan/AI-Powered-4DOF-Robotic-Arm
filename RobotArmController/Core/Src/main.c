/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
#define NUM_SERVOS         6
#define RX_BUFFER_SIZE     64

#define SERVO_MIN_US       500
#define SERVO_MAX_US       2500
#define SERVO_DEFAULT_US   1500

#define SERVO_STEP_US      10
#define UPDATE_PERIOD_MS   20

typedef struct {
    TIM_HandleTypeDef *htim;
    uint32_t channel;
} ServoMap_t;

static ServoMap_t servo_map[NUM_SERVOS];
static volatile uint16_t servo_current_us[NUM_SERVOS];
static volatile uint16_t servo_target_us[NUM_SERVOS];

static uint8_t rx_byte;
static char rx_buffer[RX_BUFFER_SIZE];
static volatile uint8_t rx_index = 0;
static volatile uint8_t line_ready = 0;
static char cmd_line[RX_BUFFER_SIZE];

#define STEPPER_MAX_SPEED_US   200
#define STEPPER_MIN_SPEED_US   2000
#define STEPPER_ACCEL_STEPS    100

static volatile int32_t stepper_current_pos = 0;
static volatile int32_t stepper_target_pos = 0;
static volatile uint8_t stepper_running = 0;
static volatile uint8_t stepper_step_state = 0;
static volatile uint32_t stepper_current_speed = STEPPER_MIN_SPEED_US;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
static void Servo_Init(void);
static void Servo_SetAngle(uint8_t idx, float angle_deg);
static void Servo_SetPulse(uint8_t idx, uint16_t pulse_us);
static void Servo_UpdateAll(void);
static void Process_Command(const char *line);
static void UART_SendString(const char *str);

static void Stepper_Init(void);
static void Stepper_MoveTo(int32_t target_step);
static void Stepper_Stop(void);
static void Stepper_Enable(uint8_t enable);

static uint16_t Pot_Read(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  MX_TIM4_Init();
  MX_USART2_UART_Init();
  MX_TIM5_Init();
  MX_ADC1_Init();
  /* USER CODE BEGIN 2 */
  Servo_Init();
    Stepper_Init();

    HAL_UART_Receive_IT(&huart2, &rx_byte, 1);

    UART_SendString("ROBOT ARM READY\r\n");

    uint32_t last_update = HAL_GetTick();

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
   while (1)
    {
      if (line_ready) {
        Process_Command(cmd_line);
        line_ready = 0;
      }

      if (HAL_GetTick() - last_update >= UPDATE_PERIOD_MS) {
        Servo_UpdateAll();
        last_update = HAL_GetTick();
      }
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 16;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV4;
  RCC_OscInitStruct.PLL.PLLQ = 7;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */
static void Servo_Init(void)
{
  servo_map[0].htim = &htim2; servo_map[0].channel = TIM_CHANNEL_1;
  servo_map[1].htim = &htim2; servo_map[1].channel = TIM_CHANNEL_2;
  servo_map[2].htim = &htim3; servo_map[2].channel = TIM_CHANNEL_1;
  servo_map[3].htim = &htim3; servo_map[3].channel = TIM_CHANNEL_2;
  servo_map[4].htim = &htim4; servo_map[4].channel = TIM_CHANNEL_1;
  servo_map[5].htim = &htim4; servo_map[5].channel = TIM_CHANNEL_2;

  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    servo_current_us[i] = SERVO_DEFAULT_US;
    servo_target_us[i]  = SERVO_DEFAULT_US;
    __HAL_TIM_SET_COMPARE(servo_map[i].htim, servo_map[i].channel, SERVO_DEFAULT_US);
    HAL_TIM_PWM_Start(servo_map[i].htim, servo_map[i].channel);
  }
}

static void Servo_SetPulse(uint8_t idx, uint16_t pulse_us)
{
  if (idx >= NUM_SERVOS) return;
  if (pulse_us < SERVO_MIN_US) pulse_us = SERVO_MIN_US;
  if (pulse_us > SERVO_MAX_US) pulse_us = SERVO_MAX_US;
  servo_target_us[idx] = pulse_us;
}

static void Servo_SetAngle(uint8_t idx, float angle_deg)
{
  if (angle_deg < 0.0f)   angle_deg = 0.0f;
  if (angle_deg > 180.0f) angle_deg = 180.0f;
  uint16_t pulse = SERVO_MIN_US +
      (uint16_t)((angle_deg / 180.0f) * (SERVO_MAX_US - SERVO_MIN_US));
  Servo_SetPulse(idx, pulse);
}

static void Servo_UpdateAll(void)
{
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    int32_t diff = (int32_t)servo_target_us[i] - (int32_t)servo_current_us[i];
    if (diff == 0) continue;

    int32_t step = (diff > 0) ? SERVO_STEP_US : -SERVO_STEP_US;
    if (abs(diff) < SERVO_STEP_US) step = diff;

    servo_current_us[i] += step;
    __HAL_TIM_SET_COMPARE(servo_map[i].htim, servo_map[i].channel,
                          servo_current_us[i]);
  }
}

static void Stepper_Init(void)
{
  HAL_GPIO_WritePin(STEPPER_EN_GPIO_Port, STEPPER_EN_Pin, GPIO_PIN_SET);
  HAL_GPIO_WritePin(STEPPER_STEP_GPIO_Port, STEPPER_STEP_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(STEPPER_DIR_GPIO_Port, STEPPER_DIR_Pin, GPIO_PIN_RESET);
}

static void Stepper_Enable(uint8_t enable)
{
  HAL_GPIO_WritePin(STEPPER_EN_GPIO_Port, STEPPER_EN_Pin,
                    enable ? GPIO_PIN_RESET : GPIO_PIN_SET);
}

static void Stepper_MoveTo(int32_t target_step)
{
  stepper_target_pos = target_step;

  if (stepper_target_pos > stepper_current_pos) {
    HAL_GPIO_WritePin(STEPPER_DIR_GPIO_Port, STEPPER_DIR_Pin, GPIO_PIN_SET);
  } else if (stepper_target_pos < stepper_current_pos) {
    HAL_GPIO_WritePin(STEPPER_DIR_GPIO_Port, STEPPER_DIR_Pin, GPIO_PIN_RESET);
  } else {
    return;
  }

  Stepper_Enable(1);

  stepper_running = 1;
  stepper_current_speed = STEPPER_MIN_SPEED_US;
  __HAL_TIM_SET_AUTORELOAD(&htim5, stepper_current_speed - 1);
  __HAL_TIM_SET_COUNTER(&htim5, 0);
  HAL_TIM_Base_Start_IT(&htim5);
}

static void Stepper_Stop(void)
{
  HAL_TIM_Base_Stop_IT(&htim5);
  stepper_running = 0;
  HAL_GPIO_WritePin(STEPPER_STEP_GPIO_Port, STEPPER_STEP_Pin, GPIO_PIN_RESET);
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  if (htim->Instance == TIM5) {
    if (!stepper_running) return;

    if (stepper_step_state == 0) {
      HAL_GPIO_WritePin(STEPPER_STEP_GPIO_Port, STEPPER_STEP_Pin, GPIO_PIN_SET);
      stepper_step_state = 1;
    } else {
      HAL_GPIO_WritePin(STEPPER_STEP_GPIO_Port, STEPPER_STEP_Pin, GPIO_PIN_RESET);
      stepper_step_state = 0;

      if (stepper_target_pos > stepper_current_pos) {
        stepper_current_pos++;
      } else if (stepper_target_pos < stepper_current_pos) {
        stepper_current_pos--;
      }

      if (stepper_current_pos == stepper_target_pos) {
        Stepper_Stop();
        return;
      }

      int32_t remaining = stepper_target_pos - stepper_current_pos;
      if (remaining < 0) remaining = -remaining;

      if (remaining < STEPPER_ACCEL_STEPS) {
        stepper_current_speed += 10;
        if (stepper_current_speed > STEPPER_MIN_SPEED_US)
          stepper_current_speed = STEPPER_MIN_SPEED_US;
      } else if (stepper_current_speed > STEPPER_MAX_SPEED_US) {
        stepper_current_speed -= 10;
      }

      __HAL_TIM_SET_AUTORELOAD(&htim5, stepper_current_speed - 1);
    }
  }
}

static uint16_t Pot_Read(void)
{
  HAL_ADC_Start(&hadc1);
  if (HAL_ADC_PollForConversion(&hadc1, 10) == HAL_OK) {
    uint16_t val = HAL_ADC_GetValue(&hadc1);
    HAL_ADC_Stop(&hadc1);
    return val;
  }
  HAL_ADC_Stop(&hadc1);
  return 0;
}

static void Process_Command(const char *line)
{
  if (line[0] == 'P') {
    UART_SendString("PONG\r\n");
    return;
  }

  if (line[0] == 'H') {
    for (uint8_t i = 0; i < NUM_SERVOS; i++) Servo_SetAngle(i, 90.0f);
    UART_SendString("OK HOME\r\n");
    return;
  }

  if (line[0] == 'S' && line[2] == ':') {
    uint8_t idx = line[1] - '0';
    float angle = atof(&line[3]);
    Servo_SetAngle(idx, angle);
    char resp[32];
    snprintf(resp, sizeof(resp), "OK S%d:%.1f\r\n", idx, angle);
    UART_SendString(resp);
    return;
  }

  if (line[0] == 'A' && line[1] == ':') {
    const char *p = &line[2];
    for (uint8_t i = 0; i < NUM_SERVOS; i++) {
      float angle = atof(p);
      Servo_SetAngle(i, angle);
      p = strchr(p, ',');
      if (!p) break;
      p++;
    }
    UART_SendString("OK ALL\r\n");
    return;
  }

  if (line[0] == 'M' && line[1] == ':') {
    int32_t target = atoi(&line[2]);
    Stepper_MoveTo(target);
    char resp[32];
    snprintf(resp, sizeof(resp), "OK M:%ld\r\n", target);
    UART_SendString(resp);
    return;
  }

  if (line[0] == 'X') {
    Stepper_Stop();
    Stepper_Enable(0);
    UART_SendString("OK STOP\r\n");
    return;
  }

  if (line[0] == 'Z') {
    stepper_current_pos = 0;
    stepper_target_pos = 0;
    UART_SendString("OK ZERO\r\n");
    return;
  }

  if (line[0] == 'Q') {
    char resp[32];
    snprintf(resp, sizeof(resp), "POS:%ld\r\n", stepper_current_pos);
    UART_SendString(resp);
    return;
  }

  if (line[0] == 'R') {
    uint16_t val = Pot_Read();
    char resp[32];
    snprintf(resp, sizeof(resp), "POT:%u\r\n", val);
    UART_SendString(resp);
    return;
  }

  UART_SendString("ERR\r\n");
}

static void UART_SendString(const char *str)
{
  HAL_UART_Transmit(&huart2, (uint8_t*)str, strlen(str), HAL_MAX_DELAY);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART2) {
    if (rx_byte == '\n' || rx_byte == '\r') {
      if (rx_index > 0) {
        rx_buffer[rx_index] = '\0';
        if (!line_ready) {
          strcpy(cmd_line, rx_buffer);
          line_ready = 1;
        }
        rx_index = 0;
      }
    } else if (rx_index < RX_BUFFER_SIZE - 1) {
      rx_buffer[rx_index++] = rx_byte;
    } else {
      rx_index = 0;
    }
    HAL_UART_Receive_IT(&huart2, &rx_byte, 1);
  }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
